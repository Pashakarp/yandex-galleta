from flask import Flask, render_template, redirect, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from data import db_session
import os

# Импорт форм из файла со всеми формами
from data.forms import AddRecipeForm, LoginForm, RegisterForm

# Импорт моделей из файла со всеми моделями
from data.models import User, Recipe

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config["IMAGE_UPLOADS"] = "static/img/uploads/"
app.config["ALLOWED_IMAGE_EXTENSIONS"] = ["PNG", "JPG", "JPEG"]
login_manager = LoginManager()
login_manager.init_app(app)


def allowed_image(filename):
    if '.' not in filename:
        return False
    ext = filename.split('.')[1]
    if ext.upper() in app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return True
    else:
        return False


db_session.global_init("db/galleta.sqlite")


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


# <---Профиль пользователя--->
@app.route('/user/<int:user_id>')
def user(user_id):
    if current_user.is_authenticated:
        session = db_session.create_session()
        user = session.query(User).filter(User.id == user_id).first()
        recipes = session.query(Recipe).filter(Recipe.user_id == user_id).all()
        if recipes:
            return render_template('user_profile.html', user=user, recipes=recipes)
        else:
            recipe_message = 'У пользователя нет рецептов'
            return render_template('user_profile.html', user=user, recipes=recipes, recipe_message=recipe_message)
    else:
        message = 'Для просмотра профиля войдите или зарегистрируйтесь'
        return render_template('user_profile.html', message=message)


# <---Основная страница--->
@app.route('/home')
def home():
    session = db_session.create_session()

    # Получение строки из поля для поиска
    q = request.args.get('q')

    if q:
        recipes = session.query(Recipe).filter(Recipe.title.contains(q) | Recipe.about.contains(q)).all()
        if not recipes:
            message = 'Ничего не найдено :('
            return render_template('home.html', recipes=recipes, title='Домашняя страница', message=message)
    else:
        recipes = session.query(Recipe).all()
    recipes = recipes[::-1]
    return render_template('home.html', recipes=recipes, title='Домашняя страница')


# <---Страница рецепта--->
@app.route('/recipe_page/<int:recipe_id>')
def recipe_page(recipe_id):
    if current_user.is_authenticated:
        session = db_session.create_session()
        recipe = session.query(Recipe).filter(Recipe.id == recipe_id).first()
        ingredients = recipe.ingredients.split('\n')
        steps = recipe.steps.split('\n')
        return render_template('recipe_page.html', recipe=recipe, ingredients=ingredients, steps=steps)
    else:
        message = 'Для просмотра рецепта войдите или зарегистрируйтесь'
        return render_template('recipe_page.html', message=message)


# <---Регистрация--->
@app.route('/register', methods=['GET', 'POST'])
def registration():
    form = RegisterForm()
    if form.validate_on_submit():
        # Проверка правильности повторного ввода пароля
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")

        # Проверка наличия в системе такого пользователя
        session = db_session.create_session()
        if session.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой пользователь уже есть")

        # Создание пользователя
        user = User(
            surname=form.surname.data,
            name=form.name.data,
            age=form.age.data,
            email=form.email.data
        )

        # Добавление пользователя в БД
        user.set_password(form.password.data)
        session.add(user)
        session.commit()

        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


# <---Вход в систему--->
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        user = session.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect("/home")
        return render_template('login.html',
                               form=form)
    return render_template('login.html', form=form)


# <---Выход из системы--->
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@login_manager.user_loader
def load_user(user_id):
    session = db_session.create_session()
    return session.query(User).get(user_id)


# <---Добавление рецепта--->
@app.route('/add_recipe', methods=['GET', 'POST'])
def add_recipe():
    form = AddRecipeForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        if session.query(Recipe).filter(Recipe.title == form.title.data).first():
            return render_template('add_recipe.html', title='Добавление рецепта',
                                   form=form, message='Такой рецепт уже есть')

        image = request.files["photo"]

        # Проверка того, что у картинки есть имя
        if image.filename == '':
            return render_template('add_recipe.html', title='Добавление рецепта',
                                   form=form, message='У картинки нет имени')

        # Проверка формата картинки
        if not allowed_image(image.filename):
            return render_template('add_recipe.html', title='Добавление рецепта',
                                   form=form, message='Доступные форматы файлов: PNG, JPG, JPEG')

        # Сохранение картинки в определенную директорию
        image.save(os.path.join(app.config["IMAGE_UPLOADS"], image.filename))
        print(f'Картинка сохранена сюда: {os.path.join(app.config["IMAGE_UPLOADS"], image.filename)}')

        recipe = Recipe(
            title=form.title.data,
            ingredients=form.ingredients.data,
            steps=form.steps.data,
            photo=os.path.join(app.config["IMAGE_UPLOADS"], image.filename),
            about=form.about.data,
            user_id=current_user.id
        )

        # Удаление пустых строк из списка шагов
        steps = recipe.steps.split('\n')
        for i in range(len(steps) - 1, -1, -1):
            if steps[i] == '' or steps[i] == '\r':
                steps.remove(steps[i])
        recipe.steps = '\n'.join(steps)

        # Удаление пустых строк из списка ингредиентов
        ingredients = recipe.ingredients.split('\n')
        for i in range(len(ingredients) - 1, -1, -1):
            if ingredients[i] == '' or ingredients[i] == '\r':
                ingredients.remove(ingredients[i])
        recipe.ingredients = '\n'.join(ingredients)

        # Добавление рецепта в БД
        session.add(recipe)
        session.commit()
        return redirect('/home')
    return render_template('add_recipe.html', title='Добавление рецепта', form=form)


# <---Удалаение рецепта--->
@app.route('/recipe_delete/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def recipe_delete(recipe_id):
    session = db_session.create_session()
    if current_user.id != 1:
        jobs = session.query(Recipe).filter(Recipe.id == recipe_id,
                                            Recipe.user == current_user).first()
    else:
        jobs = session.query(Recipe).filter(Recipe.id == recipe_id).first()

    if jobs:
        session.delete(jobs)
        session.commit()
    else:
        abort(404)
    return redirect(f'/user/{current_user.id}')


# <---Редактирование рецепта--->
@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    form = AddRecipeForm()
    if request.method == "GET":
        # Создаем словарь существующих параметров для заполнения полей
        session = db_session.create_session()
        param = session.query(Recipe).filter(Recipe.id == recipe_id).first()
        d = {'title': param.title,
             'ingredients': param.ingredients,
             'steps': param.steps,
             'photo': param.photo,
             'about': param.about}

        if current_user.id != 1:
            recipe = session.query(Recipe).filter(Recipe.id == recipe_id,
                                                  Recipe.user == current_user).first()
        else:
            recipe = session.query(Recipe).filter(Recipe.id == recipe_id).first()

        # Меняем значения на новые если рецепт получен
        if recipe:
            recipe.title = form.title.data
            recipe.ingredients = form.ingredients.data
            recipe.steps = form.steps.data
            recipe.photo = form.photo.data
            recipe.about = form.about.data
        else:
            abort(404)

    if form.validate_on_submit():
        session = db_session.create_session()
        if current_user.id != 1:
            recipe = session.query(Recipe).filter(Recipe.id == recipe_id,
                                                  Recipe.user == current_user).first()
        else:
            recipe = session.query(Recipe).filter(Recipe.id == recipe_id).first()

        image = request.files["photo"]

        # Проверка того, что у картинки есть имя
        if image.filename == '':
            return render_template('add_recipe.html', title='Добавление рецепта',
                                   form=form, message='У картинки нет имени')

        # Проверка формата картинки
        if not allowed_image(image.filename):
            return render_template('add_recipe.html', title='Добавление рецепта',
                                   form=form, message='Доступные форматы файлов: PNG, JPG, JPEG')

        # Сохранение картинки в определенную директорию
        image.save(os.path.join(app.config["IMAGE_UPLOADS"], image.filename))
        print(f'Картинка сохранена сюда: {os.path.join(app.config["IMAGE_UPLOADS"], image.filename)}')

        # На всякий случай еще раз меняем значения и подтверждаем
        if recipe:
            recipe.title = form.title.data
            recipe.ingredients = form.ingredients.data
            recipe.steps = form.steps.data
            recipe.photo = os.path.join(app.config["IMAGE_UPLOADS"], image.filename)
            recipe.about = form.about.data
            session.commit()
            return redirect(f'/user/{current_user.id}')
        else:
            abort(404)
    return render_template('add_recipe.html', title='Редактирование рецепта', form=form, param=d)


# <---О проекте--->
@app.route("/about")
def about():
    return render_template('about.html')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
