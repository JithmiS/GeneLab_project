from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Email, Length
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, render_template
from bokeh.models import (HoverTool, FactorRange, Plot, LinearAxis, Grid,
                          Range1d)
from bokeh.models.glyphs import VBar
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models.sources import ColumnDataSource
import GEOparse
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Thisissupposedtobesecret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:123@localhost/gl_db'
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember me')


class RegisterForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=50)])
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user, remember=form.remember.data)
                return redirect(url_for('data_input'))

        return '<h1>Invalid username or password</h1>'
        # return '<h1>' + form.username.data + ' ' + form.password.data + '</h1>'

    return render_template('login.html', form=form)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='sha256')
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        print ('New user has been created !!!!')
        return redirect(url_for('data_input'))
        # return '<h1>' + form.username.data + ' ' + form.email.data + ' ' + form.password.data + '</h1>'

    return render_template('signup.html', form=form)


sample_list = []
accessionId = ''
data = pd.DataFrame({'A': []})

@app.route('/data_input', methods=['GET', 'POST'])
@login_required
def data_input():
    if request.method == 'POST':
        global accessionId
        accessionId = request.form['accessionId']
        if (not get_dataframe(accessionId).empty):
            sample_list.append(get_dataframe(accessionId, True))
            print(sample_list)
            return redirect(url_for('select', accessionId=accessionId))
        else:
            return 'Error'
    return render_template('data_input.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.username)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

controls=[]

@app.route('/select', methods=['GET', 'POST'])
@login_required
def select():
    if request.method == 'POST':
        global controls
        sample1 = request.form.get('sample1')
        sample2 = request.form.get('sample2')
        controls.insert(0, sample1)
        controls.insert(0, sample2)
        print (controls)
        global data
        global accessionId
        print('start')
        print(controls)
        print('accession')
        print(accessionId)
        data = get_dataframe(accessionId)
        plot_scatter = create_scatter_plot(data)
        plot_box = create_histogram(data)
        script_scatter, div_scatter = components(plot_scatter)
        script_box, div_box = components(plot_box)

        return render_template("chart.html", bars_count='15',
                               the_div=div_scatter, the_script=script_scatter,
                               box_div=div_box, box_script=script_box, sample_list=sample_list[0],
                               sample1=sample1, sample2=sample2)
    controls=[]
    return render_template("chart.html", sample_list=sample_list[0])

def get_dataframe(accessionId, return_gse=False):
    print("[INFO] Downloading dataset...")
    isError = False
    try:
        gse = GEOparse.get_GEO(geo=str(accessionId), destdir="./")
        print("[INFO] Download complete")
        global controls
        pivoted_control_samples = gse.pivot_samples('VALUE')[controls]
        pivoted_control_samples = pivoted_control_samples.reset_index()
    except FileNotFoundError:
        isError = True
    except GEOparse.GEOparse.UnknownGEOTypeException:
        isError = True
    if (isError):
        return pd.DataFrame({'A': []})
    if (return_gse):
        return gse.show_sample_data()
    return pivoted_control_samples


def create_histogram(data):
    data = get_transposed_dataframe(data)
    sample_name = data.iloc[0, 0]
    column_names = list(data.columns)[1:100]
    values = Range1d(start=0, end=max(data.iloc[0, 1:100].values) * 1.5)

    plot = figure(plot_height=900, plot_width=900,
                  title='Histogram of ' + sample_name,
                  x_axis_label='ID_REF',
                  y_axis_label='VALUE',
                  x_range=column_names,
                  y_range=values)
    glyph = VBar(x='ID_REF', top='VALUE', bottom=0, width=.8,
                 fill_color="#e12127")
    df = pd.DataFrame()
    df['ID_REF'] = column_names
    df['VALUE'] = data.iloc[0, 1:100].values
    print(df)
    plot.add_glyph(ColumnDataSource(df), glyph)

    xaxis = LinearAxis()
    yaxis = LinearAxis()

    plot.add_layout(Grid(dimension=0, ticker=xaxis.ticker))
    plot.add_layout(Grid(dimension=1, ticker=yaxis.ticker))
    plot.toolbar.logo = None
    plot.min_border_top = 0
    plot.xgrid.grid_line_color = None
    plot.ygrid.grid_line_color = "#999999"
    plot.yaxis.axis_label = "VALUE"
    plot.ygrid.grid_line_alpha = 0.1
    plot.xaxis.axis_label = "ID_REF"
    plot.xaxis.major_label_orientation = 1
    return plot


def create_box_plot(data):
    return None


def get_transposed_dataframe(data):
    data = data.T
    data = data.reset_index()
    data.columns = data.iloc[0]
    data = pd.DataFrame(data.values[1:], columns=data.columns)
    return data


def create_scatter_plot(data):
    """Creates a bar chart plot with the exact styling for the centcom
       dashboard. Pass in data as a dictionary, desired plot title,
       name of x axis, y axis and the hover tool HTML.
    """

    source = ColumnDataSource(data=data)
    columns = list(data.columns)

    p = figure(plot_height=900, plot_width=900)
    p.circle(x=columns[1], y=columns[2],
             source=source,
             size=5, color='green')
    p.title.text = ' Scatter plot showing the correlation of gene expression between ' + columns[1] + ' and ' + columns[2]

    p.xaxis.axis_label = 'Sample ' + columns[1]
    p.yaxis.axis_label = 'Sample ' + columns[2]
    hover = HoverTool()
    hover.tooltips = [
        ('ID_REF', '@ID_REF'),
        ('Sample', columns[1]),
        ('Value', '@' + columns[1]),
        ('Sample', columns[2]),
        ('Value', '@' + columns[2]),
    ]

    p.add_tools(hover)
    return p


if __name__ == '__main__':
    app.run(debug=True)


