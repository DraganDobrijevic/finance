import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@app.route("/index.html")
@login_required
def index():
    """Show portfolio of stocks"""

    symbol = db.execute("SELECT symbol FROM names WHERE id=:id", id=session["user_id"])
    rows = []
    newSum = 0
    for dic in symbol:
        symbol = dic['symbol']
        quote = lookup(symbol)
        newPrice = quote['price']
        db.execute("UPDATE names SET newPrice=:price WHERE id=:id AND symbol=:symbol",
                   price=newPrice, id=session["user_id"], symbol=symbol)
        name = db.execute("SELECT name FROM names WHERE symbol=:symbol", symbol=symbol)
        name = name[0]['name']
        sumShares = db.execute("SELECT SUM(shares) FROM history WHERE id=:id AND symbol=:symbol",
                               id=session["user_id"], symbol=symbol)
        sumShares = sumShares[0]['SUM(shares)']
        price = db.execute("SELECT price FROM history WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)
        price = price[0]['price']
        sumTotal = db.execute("SELECT SUM(total) FROM history WHERE id=:id AND symbol=:symbol",
                              id=session["user_id"], symbol=symbol)
        sumTotal = sumTotal[0]['SUM(total)']
        newSumTotal = newPrice * sumShares
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash = cash[0]['cash']
        newSum += newSumTotal
        row = [symbol, name, sumShares, price, sumTotal]
        rows.append(row)
    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = cash[0]['cash']
    grandTotal = cash + newSum
    return render_template("index.html", rows=rows, cash=cash, TOTAL=grandTotal)


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():

    if request.method == "POST":
        addCash = request.form.get("addCash")
        if addCash != 0:
            cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
            cash = cash[0]['cash']
            cash += int(addCash)
            db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])
            return redirect("/index.html")
        else:
            return redirect("/cash.html")
    else:
        return render_template("cash.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing symbol")
        try:
            int(request.form.get("shares"))
        except ValueError:
            return apology("Please enter a positive integer")
        shares = int(request.form.get("shares"))
        if not shares or shares < 1:
            return apology("Missing shares")
        if symbol:
            quote = lookup(symbol)
            if not quote:
                return apology("Input correct symbol")
            else:
                cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
                cash = cash[0]['cash']
                price = quote['price']
                total = float(shares) * price
                if total <= cash:
                    db.execute("INSERT INTO history ('id','symbol', 'shares', 'price', 'total') VALUES (:id, :symbol, :shares, :price, :total)",
                               id=session["user_id"], symbol=quote['symbol'], shares=shares, price=price, total=total)
                    cash -= total
                    db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])
                    check = db.execute("SELECT symbol FROM names WHERE id=:id AND symbol=:symbol",
                                       id=session['user_id'], symbol=quote['symbol'])
                    if not check:
                        db.execute("INSERT INTO names ('symbol', 'name', 'id') VALUES (:symbol, :name, :id)",
                                   symbol=quote['symbol'], name=quote['name'], id=session['user_id'])
                    return redirect("index.html")
                else:
                    return apology("You don't have enough money")
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    username = request.args.get("q")
    notAvailable = db.execute("SELECT username FROM users WHERE username=:username", username=username)
    if notAvailable != []:
        return jsonify(False)
    if not username:
        return jsonify(False)
    return jsonify(True)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT * FROM history WHERE id=:id", id=session['user_id'])
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        # print(session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if symbol:
            quote = lookup(symbol)
            if not quote:
                return apology("Input correct symbol")
            else:
                return render_template("quoted.html", name=quote['name'], price=quote['price'], symbol=quote['symbol'])
        else:
            return apology("Input symbol")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()
    if request.method == "POST":
        render_template("register.html")
        username = request.form.get("username")
        notAvailable = db.execute("SELECT username FROM users WHERE username=:username", username=username)
        if notAvailable != []:
            return apology("Username is not available")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("Input username")
        if not password:
            return apology("Missing password")
        if not username and not password and not confirmation:
            return redirect("/register")
        if password != confirmation:
            return apology("The passwords do not match!!!")
        hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
        if not result:
            return apology("Try a different username.")
        #user_id = db.execute("SELECT id FROM users WHERE username = :username", username=username)
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    rows = db.execute("SELECT symbol FROM names WHERE id=:id", id=session['user_id'])
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing symbol")
        shares = int(request.form.get("shares"))
        if not shares:
            return apology("Missing shares")
        if symbol:
            quote = lookup(symbol)
            if not quote:
                return apology("Input correct symbol")
            else:
                cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
                cash = cash[0]['cash']
                price = quote['price']
                total = float(shares) * price
                myShares = db.execute("SELECT SUM(shares) FROM history WHERE id=:id AND symbol=:symbol",
                                      id=session['user_id'], symbol=quote['symbol'])
                myShares = myShares[0]["SUM(shares)"]
                if myShares > shares:
                    db.execute("INSERT INTO history ('id','symbol', 'shares', 'price', 'total') VALUES (:id, :symbol, :shares, :price, :total)",
                               id=session["user_id"], symbol=quote['symbol'], shares=-shares, price=price, total=-total)
                    cash += total
                    db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])
                    return redirect("index.html")
                elif myShares == shares:
                    #myShares -= shares
                    db.execute("INSERT INTO history ('id','symbol', 'shares', 'price', 'total') VALUES (:id, :symbol, :shares, :price, :total)",
                               id=session["user_id"], symbol=quote['symbol'], shares=-shares, price=price, total=total)
                    cash += total
                    db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])
                    db.execute("DELETE FROM names WHERE symbol=:symbol", symbol=symbol)
                    return redirect("index.html")
                else:
                    return apology("Too many shares")
    else:
        return render_template("sell.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
