import os
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userHas = 0
    user = db.execute("SELECT * FROM users WHERE id = ? ", session["user_id"])
    userCash = float(user[0]["cash"])
    userTrs = db.execute("SELECT * FROM transactions WHERE Buyer = ?",user[0]["username"])
    miscInfo = []
    seen = []
    for transaction in userTrs:
        temp = {}
        countB = db.execute("SELECT COUNT(Buyer) FROM transactions WHERE stockSymbol = ? AND opType = ? AND Buyer = ?",transaction["stockSymbol"], "Buy", user[0]["username"])
        countS = db.execute("SELECT COUNT(Buyer) FROM transactions WHERE stockSymbol = ? AND opType = ? AND Buyer = ?",transaction["stockSymbol"], "Sell", user[0]["username"])
        count = countB[0]["COUNT(Buyer)"] - countS[0]["COUNT(Buyer)"]
        look_up = lookup(transaction["stockSymbol"])
        if transaction["stockSymbol"] not in seen:
            seen.append(transaction["stockSymbol"])
            temp["Symbol"] = transaction["stockSymbol"]
            temp["Count"] = count
            temp["CurrentPrice"] = look_up["price"]
            miscInfo.append(temp)
    for ownedEle in miscInfo:
        userHas += (float(ownedEle["Count"]))*float(ownedEle["CurrentPrice"])
    return render_template("index.html", Cash=round(userCash,2), username=user[0]["username"], GrandTotal=f"{round(userHas,2)}", miscInfo=miscInfo)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        share = request.form.get("shares")
        if share.isdigit() != True:
            return apology("Invalid Share")
        elif int(share) <= 0:
            return apology("Share Can't Be Null Or Negative")
        elif not share:
            return apology("Invalid Share")
        look_up = lookup(symbol)
        if not symbol:
            return apology("Symbol Missing!")
        elif not look_up:
            return apology("Invalid Symbol!")
        else:
            print(look_up)
            user = db.execute("SELECT * FROM users WHERE id = ? ", session["user_id"])
            userCash = float(user[0]["cash"])
            stockPrice = look_up["price"]
            if userCash >= stockPrice*int(share):
                userCash -= stockPrice*int(share)
                db.execute("UPDATE users SET cash = ? WHERE id = ?",userCash,session["user_id"])
                for i in range(int(share)):
                    Time = time.localtime()
                    timeString = time.strftime("%Y-%m-%d %H:%M:%S", Time)
                    db.execute("INSERT INTO transactions (Buyer,stockSymbol,Price,Time,opType) VALUES (?, ?, ?, ?, ?)",user[0]["username"], symbol, stockPrice, timeString, "Buy")
                return render_template("buyProcess.html",symbol = symbol,shares=share,price=stockPrice*int(share), pricee = stockPrice)
            else:
                return apology("You Dont Have Enough Money")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    userTrs = db.execute("SELECT * FROM transactions WHERE Buyer = ? ", user[0]["username"])

    return render_template("history.html",userTrs=userTrs, user=user)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
        if not symbol:
            return apology("Invalid Input")
        if not lookup(symbol):
            return apology("Invalid Ticker Symbol")
        return render_template("quoted.html", symbol=symbol, look_up=lookup(symbol))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        takenNames = []
        users = db.execute("select * from users")
        for ele in users:
            takenNames.append(ele["username"])
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not name or not password or not confirmation:
            return apology("missing Input!")
        elif confirmation != password:
            return apology("Passwords don't match")
        elif name in takenNames:
            return apology("Username Taken")
        else:
            db.execute("INSERT INTO USERS (username,hash) VALUES(?,?)",name,generate_password_hash(password))
            return redirect("/login")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = db.execute("SELECT * FROM users WHERE id = ? ", session["user_id"])
    userTrs = db.execute("SELECT * FROM transactions WHERE Buyer = ?",user[0]["username"])
    userCash = float(user[0]["cash"])
    miscInfo = []
    seen = []
    for transaction in userTrs:
        temp = {}
        countB = db.execute("SELECT COUNT(Buyer) FROM transactions WHERE stockSymbol = ? AND opType = ?",transaction["stockSymbol"], "Buy")
        countS = db.execute("SELECT COUNT(Buyer) FROM transactions WHERE stockSymbol = ? AND opType = ?",transaction["stockSymbol"], "Sell")
        count = countB[0]["COUNT(Buyer)"] - countS[0]["COUNT(Buyer)"]
        look_up = lookup(transaction["stockSymbol"])

        Time = time.localtime()
        timeString = time.strftime("%Y-%m-%d %H:%M:%S", Time)

        if transaction["stockSymbol"] not in seen:
            seen.append(transaction["stockSymbol"])
            temp["Symbol"] = transaction["stockSymbol"]
            temp["Count"] = count
            temp["CurrentPrice"] = look_up["price"]
            miscInfo.append(temp)
    if request.method=="POST":
        soldSymbol = request.form.get("symbol")
        look_up = lookup(soldSymbol)
        print(soldSymbol)
        if not soldSymbol:
            return apology("Invalid Symbol")
        elif not look_up:
            return apology("Invalid Symbol")
        else:
            print(miscInfo)
            for ownedEle in miscInfo:
                print()
                print(ownedEle["Symbol"])
                print()
                if ownedEle["Symbol"] == soldSymbol:
                    if ownedEle["Count"] > 0:
                        db.execute("INSERT INTO transactions (stockSymbol,Buyer,Price,Time,opType) VALUES (?, ?, ?, ?, ?)",ownedEle["Symbol"],user[0]["username"],look_up["price"],timeString,"Sell")
                        userCash += look_up["price"]
                        db.execute("UPDATE users SET cash = ? WHERE id = ?",userCash,session["user_id"])
                        ownedEle["Count"] -= 1
                        return redirect("/")
                    else:
                        return apology("You Don't Have Enough Of This Stock")
            return apology("You Don't Have Any Of this Stock")

    else:
        return render_template("sell.html")