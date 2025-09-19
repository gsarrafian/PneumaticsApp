from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    # You can pass data into the page if you want:
    return render_template("index.html", title="Pneumatics Control")

if __name__ == '__main__':
    app.run()
