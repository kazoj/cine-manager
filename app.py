from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import random
from datetime import date
import qrcode
import io
import base64
import PIL
import os


app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')

DB_HOST = os.environ.get('DB_HOST', "postgresql-bdr.alwaysdata.net")
DB_NAME = os.environ.get('DB_NAME', "bdr_2")
DB_USER = os.environ.get('DB_USER', "bdr")


DB_PASS = os.environ.get('DB_PASS', "") 

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    
  
    cur.execute('SELECT id_film, titre, duree, studio FROM Film;')
    films = cur.fetchall()
    
    cur.close()
    conn.close()
    
  
    return render_template('index.html', liste_films=films)

@app.route('/film/<int:id_film>')
def detail_film(id_film):
    conn = get_db_connection()
    cur = conn.cursor()
    
   
    cur.execute('SELECT titre, duree, studio, nationalite, description FROM Film JOIN Genre ON Film.id_film = Genre.id_genre WHERE id_film = %s;', (id_film,))
  
    cur.execute('SELECT titre, duree, studio, nationalite, date_sortie FROM Film WHERE id_film = %s;', (id_film,))
    film = cur.fetchone()
    
   
    cur.execute('''
        SELECT s.id_seance, s.date, s.heure, sa.nom_salle, s.places_disponibles 
        FROM Seance s
        JOIN Salle sa ON s.id_salle = sa.id_salle
        WHERE s.id_film = %s
        ORDER BY s.date, s.heure;
    ''', (id_film,))
    seances = cur.fetchall()
    
    cur.close()
    conn.close()
    
   
    if film is None:
        return "Film introuvable", 404
        
    return render_template('detail.html', film=film, seances=seances)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        mdp = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        
        cur.execute("""
            SELECT c.id_client, i.prenom 
            FROM Client c
            JOIN Individu i ON c.id_client = i.id_individu
            WHERE c.email = %s AND c.mot_de_passe = %s
        """, (email, mdp))
        
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
        
            session['user_id'] = user[0]
            session['prenom'] = user[1]
            return redirect(url_for('index'))
        else:
        
            flash("Email ou mot de passe incorrect !", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('index'))
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    
    cur.execute("""
        SELECT r.id_reservation, f.titre, s.date, s.heure, 
               CASE WHEN r.validite THEN 'Valide' ELSE 'Utilisé/Expiré' END,
               sa.nom_salle
        FROM Reservation r
        JOIN Seance s ON r.id_seance = s.id_seance
        JOIN Film f ON s.id_film = f.id_film
        JOIN Salle sa ON s.id_salle = sa.id_salle
        WHERE r.id_client = %s
        ORDER BY r.date_reservation DESC;
    """, (session['user_id'],))
    
    billets = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', billets=billets)

@app.route('/reserver/<int:id_seance>')
def reserver(id_seance):
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour réserver.", "warning")
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
    
        cur.execute("SELECT places_disponibles FROM Seance WHERE id_seance = %s", (id_seance,))
        places = cur.fetchone()[0]
        
        if places <= 0:
            flash("Désolé, cette séance est complète !", "danger")
            return redirect(url_for('index'))

        
        id_ticket = random.randint(100000, 999999)
        
       
        today = date.today()
        cur.execute("""
            INSERT INTO Reservation (id_reservation, date_reservation, validite, id_seance, id_client)
            VALUES (%s, %s, TRUE, %s, %s)
        """, (id_ticket, today, id_seance, session['user_id']))
        

        cur.execute("UPDATE Seance SET places_disponibles = places_disponibles - 1 WHERE id_seance = %s", (id_seance,))
        
        conn.commit() 
        flash(f"Réservation réussie ! Votre billet est le #{id_ticket}", "success")
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        conn.rollback() 
        print(e)
        flash("Une erreur technique est survenue.", "danger")
        return redirect(url_for('index'))
        
    finally:
        cur.close()
        conn.close()

@app.template_filter('qr_base64')
def qr_base64(data):
    img = qrcode.make(str(data))
    
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    

    return base64.b64encode(img_io.getvalue()).decode('utf-8')

if __name__ == '__main__':
    app.run(debug=True)
