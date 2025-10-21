from flask import Flask
from a import login_bp
from calendar import calendar_bp
from insert import insert_bp

app = Flask(__name__)

# Blueprint登録
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)

if __name__ == '__main__':
    app.run(debug=True)
