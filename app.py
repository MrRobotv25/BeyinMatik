from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

# PostgreSQL URL düzeltme
uri = os.environ.get('DATABASE_URL')
if uri:
    if uri.startswith('postgres://'):
        uri = uri.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///beyinmatik.db'

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_random_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True)
    class_level = db.Column(db.String(10), default="5")
    solution_count = db.Column(db.Integer, default=0)
    rank = db.Column(db.String(50), default="Çaylak Üye")
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(200), nullable=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_level = db.Column(db.String(10), nullable=False)
    posts = db.relationship('Post', backref='category', lazy=True)
    units = db.relationship('Unit', backref='category', lazy=True)

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    posts = db.relationship('Post', backref='unit', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))
    is_solved = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='post', lazy=True)
    likes = db.relationship('Like', backref='post', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    is_solution = db.Column(db.Boolean, default=False)
    likes = db.relationship('Like', backref='comment', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    date_liked = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(200))
    link = db.Column(db.String(200))
    seen = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def update_rank(user):
    if user.is_admin:
        user.rank = "FORUM KURUCUSU"
    elif user.solution_count >= 20:
        user.rank = "Usta Üye"
    elif user.solution_count >= 10:
        user.rank = "Zeki Üye"
    elif user.solution_count >= 5:
        user.rank = "Aktif Üye"
    else:
        user.rank = "Çaylak Üye"
    db.session.commit()

def init_categories():
    categories_data = {
        "5": {
            "Matematik": ["Doğal Sayılar", "Kesirler", "Ondalık Gösterim", "Temel Geometri"],
            "Türkçe": ["Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam", "Dil Bilgisi"],
            "Fen Bilimleri": ["Güneş, Dünya ve Ay", "Canlılar Dünyası", "Kuvvetin Ölçülmesi", "Madde ve Değişim"],
            "Sosyal Bilgiler": ["Haklarımı Öğreniyorum", "Adım Adım Türkiye", "Bölgemizi Tanıyalım", "Üretim, Dağıtım ve Tüketim"]
        },
        "6": {
            "Matematik": ["Kesirlerle İşlemler", "Ondalık Gösterim", "Oran", "Cebirsel İfadeler"],
            "Türkçe": ["Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam", "Yazım Kuralları"],
            "Fen Bilimleri": ["Güneş Sistemi ve Tutulmalar", "Vücudumuzdaki Sistemler", "Kuvvet ve Hareket", "Madde ve Isı"],
            "Sosyal Bilgiler": ["Birey ve Toplum", "Kültür ve Miras", "İnsanlar, Yerler ve Çevreler", "Bilim, Teknoloji ve Toplum"]
        },
        "7": {
            "Matematik": ["Tam Sayılarla İşlemler", "Rasyonel Sayılar", "Cebirsel İfadeler", "Eşitlik ve Denklem"],
            "Türkçe": ["Fiiller", "Zarflar", "Paragrafta Anlam", "Anlatım Bozuklukları"],
            "Fen Bilimleri": ["Güneş Sistemi ve Ötesi", "Hücre ve Bölünmeler", "Kuvvet ve Enerji", "Saf Madde ve Karışımlar"],
            "Sosyal Bilgiler": ["İletişim ve İnsan İlişkileri", "Ülkemizde Nüfus", "Türk Tarihinde Yolculuk", "Zaman İçinde Bilim"]
        },
        "8": {
            "Matematik": ["Çarpanlar ve Katlar", "Üslü İfadeler", "Kareköklü İfadeler", "Veri Analizi"],
            "Türkçe": ["Cümlenin Ögeleri", "Fiilimsiler", "Yazım Kuralları", "Anlatım Türleri"],
            "Fen Bilimleri": ["Mevsimler ve İklim", "DNA ve Genetik Kod", "Basınç", "Madde ve Endüstri"],
            "Sosyal Bilgiler": ["Bir Kahraman Doğuyor", "Milli Uyanış", "Atatürkçülük", "Demokratikleşme Çabaları"]
        },
        "Genel": {
            "Genel Tartışma": ["Tanışma", "Duyurular", "Öneri ve Şikayetler", "Genel Tartışma"],
            "Rehberlik": ["Ders Çalışma Teknikleri", "Sınav Kaygısı", "Hedef Belirleme", "Meslek Tanıtımı"]
        }
    }
    
    for class_level, categories in categories_data.items():
        for category_name, units in categories.items():
            category = Category.query.filter_by(name=category_name, class_level=class_level).first()
            if not category:
                category = Category(name=category_name, class_level=class_level)
                db.session.add(category)
                db.session.commit()
            
            for unit_name in units:
                unit = Unit.query.filter_by(name=unit_name, category_id=category.id).first()
                if not unit:
                    unit = Unit(name=unit_name, category_id=category.id)
                    db.session.add(unit)
    
    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        class_level = request.form['class_level']
        
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor!', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(username=username, password=password, class_level=class_level)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if user.is_banned:
                flash('Hesabınız banlanmış! Sebep: ' + (user.ban_reason or 'Belirtilmemiş'), 'danger')
                return redirect(url_for('login'))
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('forum'))
        else:
            flash('Hatalı kullanıcı adı veya şifre', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/forum')
@login_required
def forum():
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Foruma erişim izniniz yok.', 'danger')
        return redirect(url_for('logout'))
        
    class_level = request.args.get('class_level', current_user.class_level)
    category_id = request.args.get('category_id', type=int)
    unit_id = request.args.get('unit_id', type=int)
    search_query = request.args.get('q', '')
    
    query = Post.query.join(User).filter(User.is_banned == False)
    
    if class_level and class_level != 'Hepsi':
        query = query.join(Category).filter(Category.class_level == class_level)
    
    if category_id:
        query = query.filter(Post.category_id == category_id)
    
    if unit_id:
        query = query.filter(Post.unit_id == unit_id)
    
    if search_query:
        query = query.filter(Post.title.ilike(f'%{search_query}%') | Post.content.ilike(f'%{search_query}%'))
    
    posts = query.order_by(Post.is_pinned.desc(), Post.date_posted.desc()).all()
    
    categories = Category.query.all()
    units = Unit.query.all()
    
    return render_template('forum.html', posts=posts, categories=categories, units=units, 
                          class_level=class_level, category_id=category_id, unit_id=unit_id)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Konu açamazsınız.', 'danger')
        return redirect(url_for('logout'))
        
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category_id = request.form['category_id']
        unit_id = request.form['unit_id']
        
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_filename = get_random_filename(filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        
        post = Post(
            title=title, 
            content=content, 
            user_id=current_user.id, 
            category_id=category_id, 
            unit_id=unit_id,
            image=image_filename
        )
        db.session.add(post)
        db.session.commit()
        
        flash('Konunuz başarıyla oluşturuldu!', 'success')
        return redirect(url_for('view_post', post_id=post.id))
    
    categories = Category.query.filter(
        (Category.class_level == current_user.class_level) | 
        (Category.class_level == 'Genel')
    ).all()
    
    units = Unit.query.join(Category).filter(
        (Category.class_level == current_user.class_level) | 
        (Category.class_level == 'Genel')
    ).all()
    
    return render_template('create_post.html', categories=categories, units=units)

@app.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Konuları görüntüleyemezsiniz.', 'danger')
        return redirect(url_for('logout'))
        
    post = Post.query.get_or_404(post_id)
    if post.author.is_banned:
        flash('Bu konunun yazarı banlanmış!', 'warning')
        return redirect(url_for('forum'))
        
    return render_template('post.html', post=post)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Yorum yapamazsınız.', 'danger')
        return redirect(url_for('logout'))
        
    content = request.form['content']
    
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_filename = get_random_filename(filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
    
    comment = Comment(
        content=content, 
        user_id=current_user.id, 
        post_id=post_id,
        image=image_filename
    )
    db.session.add(comment)
    
    post = Post.query.get(post_id)
    if post.author.id != current_user.id:
        notification = Notification(
            user_id=post.author.id,
            message=f"{current_user.username} konunuza yorum yaptı!",
            link=f"/post/{post_id}"
        )
        db.session.add(notification)
    
    db.session.commit()
    
    flash('Yorumunuz eklendi!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/mark_solution/<int:comment_id>')
@login_required
def mark_solution(comment_id):
    if current_user.is_banned:
        flash('Hesabınız banlanmış! İşlem yapamazsınız.', 'danger')
        return redirect(url_for('logout'))
        
    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get_or_404(comment.post_id)
    
    if post.author.id != current_user.id:
        flash('Sadece konu sahibi çözüm işaretleyebilir.', 'danger')
        return redirect(url_for('view_post', post_id=post.id))
    
    for c in post.comments:
        c.is_solution = False
    
    comment.is_solution = True
    post.is_solved = True
    
    comment.author.solution_count += 1
    update_rank(comment.author)
    
    notification = Notification(
        user_id=comment.author.id,
        message=f"{current_user.username} yorumunuzu çözüm olarak işaretledi!",
        link=f"/post/{post.id}"
    )
    db.session.add(notification)
    
    db.session.commit()
    
    flash('Çözüm olarak işaretlendi!', 'success')
    return redirect(url_for('view_post', post_id=post.id))

@app.route('/like/<string:item_type>/<int:item_id>')
@login_required
def like_item(item_type, item_id):
    if current_user.is_banned:
        return jsonify({'success': False, 'message': 'Hesabınız banlanmış!'})
        
    if item_type == 'post':
        item = Post.query.get_or_404(item_id)
        existing_like = Like.query.filter_by(user_id=current_user.id, post_id=item_id).first()
    elif item_type == 'comment':
        item = Comment.query.get_or_404(item_id)
        existing_like = Like.query.filter_by(user_id=current_user.id, comment_id=item_id).first()
    else:
        return jsonify({'success': False, 'message': 'Geçersiz tip'})
    
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        new_like = Like(user_id=current_user.id)
        if item_type == 'post':
            new_like.post_id = item_id
        else:
            new_like.comment_id = item_id
        db.session.add(new_like)
        liked = True
        
        if item.author.id != current_user.id:
            notification = Notification(
                user_id=item.author.id,
                message=f"{current_user.username} içeriğinizi beğendi!",
                link=f"/post/{item.post_id if item_type == 'comment' else item.id}"
            )
            db.session.add(notification)
    
    db.session.commit()
    
    like_count = len(item.likes)
    
    return jsonify({
        'success': True, 
        'liked': liked, 
        'like_count': like_count
    })

@app.route('/profile/<username>')
@login_required
def profile(username):
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Profilleri görüntüleyemezsiniz.', 'danger')
        return redirect(url_for('logout'))
        
    user = User.query.filter_by(username=username).first_or_404()
    if user.is_banned:
        flash('Bu kullanıcı banlanmış!', 'warning')
        return redirect(url_for('forum'))
        
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.date_posted.desc()).limit(10).all()
    comments = Comment.query.filter_by(user_id=user.id).order_by(Comment.date_posted.desc()).limit(10).all()
    
    return render_template('profile.html', user=user, posts=posts, comments=comments)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Profil düzenleyemezsiniz.', 'danger')
        return redirect(url_for('logout'))
        
    if request.method == 'POST':
        # Profil fotoğrafı yükleme
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                profile_filename = get_random_filename(filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], profile_filename))
                
                # Eski fotoğrafı sil
                if current_user.profile_picture:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_picture))
                    except:
                        pass
                
                current_user.profile_picture = profile_filename
        
        # Şifre değiştirme
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password = generate_password_hash(new_password)
        
        db.session.commit()
        flash('Profil başarıyla güncellendi!', 'success')
    
    return redirect(url_for('profile', username=current_user.username))

@app.route('/notifications')
@login_required
def get_notifications():
    if current_user.is_banned:
        return jsonify([])
        
    notifications = Notification.query.filter_by(user_id=current_user.id, seen=False).order_by(Notification.date_created.desc()).all()
    
    notif_list = [{
        "id": n.id, 
        "message": n.message, 
        "link": n.link,
        "date_created": n.date_created.strftime('%d.%m.%Y %H:%M')
    } for n in notifications]
    
    for n in notifications:
        n.seen = True
    
    db.session.commit()
    
    return jsonify(notif_list)

@app.route('/leaderboard')
@login_required
def leaderboard():
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Liderlik tablosunu görüntüleyemezsiniz.', 'danger')
        return redirect(url_for('logout'))
        
    users = User.query.filter_by(is_banned=False).order_by(User.solution_count.desc()).all()
    return render_template('leaderboard.html', users=users)

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Admin erişiminiz yok!', 'danger')
        return redirect(url_for('forum'))
    
    users = User.query.all()
    posts = Post.query.all()
    categories = Category.query.all()
    
    return render_template('admin.html', users=users, posts=posts, categories=categories)

@app.route('/ban_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def ban_user(user_id):
    if not current_user.is_admin:
        flash('Admin erişiminiz yok!', 'danger')
        return redirect(url_for('forum'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        ban_reason = request.form.get('ban_reason', '')
        user.is_banned = True
        user.ban_reason = ban_reason
        db.session.commit()
        
        flash(f'{user.username} kullanıcısı banlandı! Sebep: {ban_reason}', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('ban_user.html', user=user)

@app.route('/unban_user/<int:user_id>')
@login_required
def unban_user(user_id):
    if not current_user.is_admin:
        flash('Admin erişiminiz yok!', 'danger')
        return redirect(url_for('forum'))
    
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.ban_reason = None
    db.session.commit()
    
    flash(f'{user.username} kullanıcısının banı kaldırıldı!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/pin_post/<int:post_id>')
@login_required
def pin_post(post_id):
    if not current_user.is_admin:
        flash('Admin erişiminiz yok!', 'danger')
        return redirect(url_for('forum'))
    
    post = Post.query.get_or_404(post_id)
    post.is_pinned = True
    db.session.commit()
    
    flash('Konu sabitlendi!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/unpin_post/<int:post_id>')
@login_required
def unpin_post(post_id):
    if not current_user.is_admin:
        flash('Admin erişiminiz yok!', 'danger')
        return redirect(url_for('forum'))
    
    post = Post.query.get_or_404(post_id)
    post.is_pinned = False
    db.session.commit()
    
    flash('Konu sabitlenmekten çıkarıldı!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if current_user.is_admin or post.author.id == current_user.id:
        Comment.query.filter_by(post_id=post_id).delete()
        Like.query.filter_by(post_id=post_id).delete()
        
        if post.image:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.image))
            except:
                pass
        
        db.session.delete(post)
        db.session.commit()
        
        flash('Konu başarıyla silindi!', 'success')
    else:
        flash('Bu işlem için yetkiniz yok!', 'danger')
    
    return redirect(url_for('forum'))

@app.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id
    
    if current_user.is_admin or comment.author.id == current_user.id:
        Like.query.filter_by(comment_id=comment_id).delete()
        
        if comment.image:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], comment.image))
            except:
                pass
        
        db.session.delete(comment)
        db.session.commit()
        
        flash('Yorum başarıyla silindi!', 'success')
    else:
        flash('Bu işlem için yetkiniz yok!', 'danger')
    
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    if current_user.is_banned:
        flash('Hesabınız banlanmış! Konu düzenleyemezsiniz.', 'danger')
        return redirect(url_for('logout'))
        
    post = Post.query.get_or_404(post_id)
    
    if not (current_user.is_admin or post.author.id == current_user.id):
        flash('Bu işlem için yetkiniz yok!', 'danger')
        return redirect(url_for('view_post', post_id=post_id))
    
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.category_id = request.form['category_id']
        post.unit_id = request.form['unit_id']
        
        if 'remove_image' in request.form and post.image:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.image))
            except:
                pass
            post.image = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                if post.image:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.image))
                    except:
                        pass
                
                filename = secure_filename(file.filename)
                post.image = get_random_filename(filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], post.image))
        
        db.session.commit()
        flash('Konu başarıyla güncellendi!', 'success')
        return redirect(url_for('view_post', post_id=post_id))
    
    categories = Category.query.all()
    units = Unit.query.all()
    
    return render_template('edit_post.html', post=post, categories=categories, units=units)

@app.route('/get_units/<int:category_id>')
@login_required
def get_units(category_id):
    units = Unit.query.filter_by(category_id=category_id).all()
    units_list = [{'id': unit.id, 'name': unit.name} for unit in units]
    return jsonify(units_list)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def create_database():
    with app.app_context():
        db.create_all()
        init_categories()
        
        if not User.query.filter_by(username='Yönetici').first():
            admin_user = User(
                username='Yönetici', 
                password=generate_password_hash('admin123'),
                class_level='Genel',
                is_admin=True,
                rank='FORUM KURUCUSU'
            )
            db.session.add(admin_user)
            db.session.commit()
        
        print("Veritabanı başarıyla oluşturuldu!")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    create_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
