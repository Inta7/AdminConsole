from flask import Flask, redirect, url_for
from flask import render_template, make_response
from flask import request
from flask import send_file
from flask import json, Markup
import json
import time
import requests
import urllib3
import datetime
import os
from contextlib import closing
import pymysql
from ldap3 import Server, Connection, ALL, SUBTREE, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException, LDAPBindError
import uuid



app = Flask(__name__)


db_host = 'test.test.ru'
db_login = 'testlogin'
db_password = 'testpassword'
db = 'testdb'

@app.template_filter('jsonify')
def jsonify_filter(s):
    return Markup(json.dumps(s, indent=4, ensure_ascii=False))


def menu(title, login):
    menu = []
    with closing(pymysql.connect(host=db_host, user=db_login, password=db_password, db=db)) as connection:
        connection.autocommit(True)
        with connection.cursor() as query:
            sql_query = f"""
                        select distinct m.name, m.link from admin_sessions s inner join admin_sessions_roles sr on s.login = sr.login
                        inner join admin_roles_menu rm on rm.role = sr.role
                        inner join admin_menu m on m.id = rm.menu
                        where s.login = '{login}'
            """
            query.execute(sql_query)
            for item in query.fetchall():
                item_struct = {}
                item_struct['title'] = item[0]
                item_struct['href'] = item[1]
                if item[0] == title:
                    item_struct['active'] = 'active'
                menu.append(item_struct)
    return menu

def update_timeout(login, session_key):
    with closing(pymysql.connect(host=db_host, user=db_login, password=db_password, db=db)) as connection:
        connection.autocommit(True)
        with connection.cursor() as query:
            sql_query = f"""
                        update admin_sessions set expired = '{format(datetime.datetime.now() + datetime.timedelta(hours=1), '%Y-%m-%d %H:%M:%S')}'
                        where login = '{login}' and session_key = '{session_key}'
            """
            query.execute(sql_query)


def menu_allowed(title, login, session_key):
    with closing(pymysql.connect(host=db_host, user=db_login, password=db_password, db=db)) as connection:
        connection.autocommit(True)
        with connection.cursor() as query:
            sql_query = f"""
                        select count(*) from admin_sessions s inner join admin_sessions_roles sr on s.login = sr.login
                        inner join admin_roles_menu rm on rm.role = sr.role
                        inner join admin_menu m on m.id = rm.menu
                        where m.name = '{title}' and s.login = '{login}' and s.session_key = '{session_key}' and s.expired > '{format(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')}'
            """
            query.execute(sql_query)
            res = query.fetchone()[0]

    if res > 0:
        return True
    else:
        return False
    
def add_file_to_json(filename, path):
    with open(json_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    file_name_without_extension = os.path.splitext(filename)[0]
    if path in data:
        data[path].append(file_name_without_extension)
    else:
        data[path] = [file_name_without_extension]
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def get_file_content(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            if not content.strip():
                return {}
            if content.strip()[0] not in ["{", "["]:
                return {}
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_file_content(file_path, content):
    try:
       with open(file_path, "w", encoding="utf-8") as file:
           json.dump(content, file, indent=4, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return False, str(e)
    return True, None


def list_files_in_directory(directory):
    files = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        files.append((filename, file_path))
    return files


with open("C:/Users/test/config/config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)
    path = config.get("path", "")
    root_directory = config.get("root_directory", "")
    json_file_path = config.get("json_file_path", "")


@app.route('/')
@app.route('/index/')
def index():
    title = 'Главная'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
        update_timeout(login, session_key)
        return render_template("index.html")
    else:
        return render_template('login.html')
    

@app.route('/sales/')
def sales():
    title = 'Sales'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
        update_timeout(login, session_key)
        with open(path, 'r', encoding="utf-8") as f:
            data = json.load(f)
        return render_template('sales.html', data=data)
    else:
        return render_template('login.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    data = request.form
    try:
        domain_parts = data['domain'].split('.')
        domain = domain_parts[0]
        domain0 = domain_parts[1]
    except:
        domain = data['domain']
        domain0 = 'local'

    username = data['username']
    password = data['password']

    server_url = f'ldap://test.test.ru'
    user_name = f'{username}@{domain}.{domain0}'
    search_base = f'dc={domain},dc={domain0}'
    search_filter = f'(sAMAccountName={username})'

    try:
        server = Server(server_url, get_info=ALL)
        c = Connection(server, user=user_name, password=password)
        bind_responce = c.bind()
        c.search(search_base=search_base,
                 search_filter=search_filter,
                 search_scope=SUBTREE,
                 get_operational_attributes=True,
                 attributes=['memberOf'])
        try:
            groups = []
            for item in c.response[0]['attributes']['memberOf']:
                l = item.split(',')
                s = {}
                for il in l:
                    sil = il.split('=')
                    s[sil[0]] = sil[1]
                groups.append(s['CN'])
            sep = '", "'
            group_list = f'"{sep.join(groups)}"'
            session_key = uuid.uuid4()
            with closing(pymysql.connect(host=db_host, user=db_login, password=db_password, db=db)) as connection:
                connection.autocommit(True)
                with connection.cursor() as query:
                    sql_query = f"delete from admin_sessions where login = '{username}'"
                    query.execute(sql_query)

                    sql_query = f"""
                                insert into admin_sessions
                                select distinct '{username}' as login, '{session_key}' as session_key, '{format(datetime.datetime.now() + datetime.timedelta(hours=1), '%Y-%m-%d %H:%M:%S')}' as expired
                                from admin_roles_cn where cn in ({group_list})
                    """
                    query.execute(sql_query)

                    sql_query = f"""
                                insert into admin_sessions_roles
                                select distinct '{username}' as login, role from admin_roles_cn
                                inner join admin_sessions on admin_sessions.login = '{username}'
                                where cn in ({group_list})
                    """
                    query.execute(sql_query)

                    sql_query = f"""
                                select * from admin_sessions_roles where login = '{username}'
                    """
                    query.execute(sql_query)
                    if len(query.fetchall()) > 0:
                        rsp = redirect('/index')
                        rsp.set_cookie('login', username)
                        rsp.set_cookie('session_key', str(session_key))
                        return rsp
                    else:
                        error = 'У вас нет прав для использования этого портала'
                        return render_template('login.html', error = error)
        except Exception as e:
            error = 'Неверный логин или пароль'
            return render_template('login.html', error = error)
    except Exception as e:
        error = 'У вас нет прав для использования этого портала'
        return render_template('login.html', error = error)


@app.route('/logoff/', methods=['GET', 'POST'])
def logoff():
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')

    with closing(pymysql.connect(host=db_host, user=db_login, password=db_password, db=db)) as connection:
        connection.autocommit(True)
        with connection.cursor() as query:
            sql_query = f"""
                        delete from admin_sessions where login = '{login}' and session_key = '{session_key}'
            """
            query.execute(sql_query)
    return render_template('login.html')


@app.route('/edit/', methods=['GET', 'POST'])
def edit():
    title = 'Редактировать'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
        update_timeout(login, session_key)
        index = int(request.args.get('index'))
        with open(path, 'r') as f:
            data = json.load(f)

        if index >= len(data['indicators']):
            return render_template('edit.html', index=index, error='Индикатор не найден')

        if request.method == 'POST':
            system = request.form['system']
            system_part = request.form['system_part']
            product = request.form['product']
            delta = request.form['delta'].replace(',', '.')
            if delta.replace('.', '', 1).isdigit():
                delta = float(delta)
            warning_time = request.form['warning_time']
            critical_time = request.form['critical_time']
            baseline = request.form['baseline'].replace(',', '.')
            if baseline.replace('.', '', 1).isdigit():
                baseline = float(baseline)
            null_warning_time = request.form['null_warning_time']
            null_critical_time = request.form['null_critical_time']

            if not delta or not warning_time or not critical_time or not baseline or not null_warning_time or not null_critical_time:
                return render_template('edit.html', index=index, error='Заполните обязательные поля',
                                       indicator=data['indicators'][index])

            delta = float(delta)
            warning_time = int(warning_time)
            critical_time = int(critical_time)
            baseline = float(baseline)
            null_warning_time = int(null_warning_time)
            null_critical_time = int(null_critical_time)

            if not 0 <= baseline <= 1 or not 0 <= delta <= 1:
                return redirect('/sales')

            data['indicators'][index]['system'] = system
            data['indicators'][index]['system_part'] = system_part
            data['indicators'][index]['product'] = product
            data['indicators'][index]['count']['delta'] = delta
            data['indicators'][index]['count']['warning_time'] = warning_time
            data['indicators'][index]['count']['critical_time'] = critical_time
            data['indicators'][index]['null']['baseline'] = baseline
            data['indicators'][index]['null']['warning_time'] = null_warning_time
            data['indicators'][index]['null']['critical_time'] = null_critical_time

            with open(path, 'w') as f:
                json.dump(data, f, indent=4)

            return redirect('/sales')
        else:
            indicator = data['indicators'][index]
            return render_template('edit.html', index=index, error='', indicator=indicator)
    else:
        return render_template('login.html')


@app.route('/create/', methods=['GET', 'POST'])
def create():
    title = 'Создать'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
       update_timeout(login, session_key)

       if request.method == 'POST':
           system = request.form['system']
           system_part = request.form['system_part']
           product = request.form['product']
           delta = request.form['delta'].replace(',', '.')
           if delta.replace('.', '', 1).isdigit():
               delta = float(delta)
           warning_time = request.form['warning_time']
           critical_time = request.form['critical_time']
           baseline = request.form['baseline'].replace(',', '.')
           if baseline.replace('.', '', 1).isdigit():
               baseline = float(baseline)
           null_warning_time = request.form['null_warning_time']
           null_critical_time = request.form['null_critical_time']

           if not delta or not warning_time or not critical_time or not baseline or not null_warning_time or not null_critical_time:
               return render_template('create.html', error='Заполните обязательные поля')

           delta = float(delta)
           warning_time = int(warning_time)
           critical_time = int(critical_time)
           baseline = float(baseline)
           null_warning_time = int(null_warning_time)
           null_critical_time = int(null_critical_time)

           if not 0 <= baseline <= 1 or not 0 <= delta <= 1:
               return redirect('/sales')

           new_indicator = {
               'system': system,
               'system_part': system_part,
               'product': product,
               'count': {
                   'delta': delta,
                   'warning_time': warning_time,
                   'critical_time': critical_time
               },
               'null': {
                   'baseline': baseline,
                   'warning_time': null_warning_time,
                   'critical_time': null_critical_time
               }
           }

           with open(path, 'r') as f:
               data = json.load(f)

           data['indicators'].append(new_indicator)

           with open(path, 'w') as f:
               json.dump(data, f, indent=4)

           return redirect('/sales')
       else:
           return render_template('create.html', error='')


@app.route('/delete/', methods=['GET', 'POST'])
def delete():
    if request.method == 'POST':
       index = int(request.form['index'])
    else:
       index = int(request.args.get('index'))

    with open(path, 'r') as f:
       data = json.load(f)

    del data['indicators'][index]

    with open(path, 'w') as f:
       json.dump(data, f, indent=4)

    return redirect('/sales')


@app.route("/group", defaults={"path": ""})
@app.route("/<path:path>")
def show_directory_content(path):
    full_path = os.path.join(root_directory, path)
    if os.path.isdir(full_path):
        files = list_files_in_directory(full_path)
        return render_template("directory.html", directory=path, files=files, os=os)
    elif os.path.isfile(full_path):
        content = get_file_content(full_path)
        return render_template("edit_file.html", file=path, content=content, os=os)
    else:
        return "File not found", 404


@app.route("/create_folder/", methods=["POST"])
def create_folder():
    title = 'СоздатьПапку'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
       update_timeout(login, session_key)
       if request.method == "POST":
           foldername = request.form["foldername"]
           path = request.form["path"]  
           full_path = os.path.join(root_directory, path, foldername)
           if not os.path.exists(full_path):
               os.makedirs(full_path)
               return redirect(url_for("show_directory_content", path=path))  
       else:
           path = request.args.get("path", "")  
       return render_template("create_file.html", directory=path)  
    else:
        return render_template("login.html")


@app.route("/create_file/", methods=["GET", "POST"])
def create_file():
    title = 'СоздатьФайл'
    login = request.cookies.get('login')
    session_key = request.cookies.get('session_key')
    if menu_allowed(title, login, session_key):
       update_timeout(login, session_key)
       if request.method == "POST":
           action = request.form["action"]
           filename = request.form["name"] 
           path = request.form["path"]
           full_path = os.path.join(root_directory, path, filename)
           if not os.path.exists(full_path):
               if action == "Создать":
                   with open(full_path, "w") as file:
                       pass
                   add_file_to_json(filename, path)
               elif action == "Сoздать":
                   os.makedirs(full_path)
               return redirect(url_for("show_directory_content", path=path))
       else:
           path = request.args.get("path", "")
       return render_template("create_file.html", directory=path, is_inside_root=path == "")
    return render_template("login.html")



@app.route("/save/<path:path>", methods=["POST"])
def save_file(path):
    full_path = os.path.join(root_directory, path)
    if os.path.isfile(full_path):
        content = request.form["content"]
        
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            error_message = "Некорректный формат JSON"
            return render_template("edit_file.html", file=path, content=content, os=os, error_message=error_message)

        save_file_content(full_path, content)
    
    return redirect(url_for("show_directory_content", path=os.path.dirname(path)))


@app.route("/delete_file/", methods=["DELETE"])
def delete_file():
    path = request.args.get("path")
    file = request.args.get("file")
    full_path = os.path.join(root_directory, path, file)

    try:
        os.remove(full_path)
        return "File deleted successfully", 200
    except OSError:
        return "Failed to delete the file", 500




if __name__ == '__main__':
    app.run(debug=True)