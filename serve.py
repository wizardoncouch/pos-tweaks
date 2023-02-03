from waitress import serve


from app import app

serve(app=app, host='0.0.0.0', port=8080, threads=1)