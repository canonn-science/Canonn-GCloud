from flask import current_app
from flask import request

app = current_app


@app.route("/hello/<name>")
def hello(name=None):
    system = request.args.get("system", 'Sol')
    return f"Hello {name} from {system}"


@app.route("/goodbye", methods=['POST'])
def goodbye():
    return "Goodbye World"


@app.route("/")
def root():
    return "root"


if __name__ == "__main__":
    app.run(debug=False)


def main(request):
    return "what happen"
