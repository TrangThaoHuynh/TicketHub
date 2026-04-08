class Config:
    SECRET_KEY = "tickethub-secret-key"

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:123456@localhost/ticketdb"
    SQLALCHEMY_TRACK_MODIFICATIONS = False