from flask import current_app
from flask import request
from localpackage.canonn import silly

app = current_app


@app.route("/hello/<name>")
def hello(name=None):
    system = request.args.get("system", 'Sol')
    return f"Hello {name} from {system}"


@app.route("/goodbye", methods=['GET'])
def goodbye():
    return request.args


@app.route("/canonn")
def external():
    return silly(request)


@app.route("/")
def root():
    return "root"


# if __name__ == "__main__":
#    app.run(debug=False)


def payload(request):
    return "what happen"
