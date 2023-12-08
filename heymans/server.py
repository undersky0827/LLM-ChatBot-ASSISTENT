import random
import markdown
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, Response, render_template, \
    redirect, url_for
from flask_login import login_user, LoginManager, UserMixin, login_required, \
    current_user, logout_user
from .forms import LoginForm
import logging
import time
from . import config
from . import utils
from .heymans import Heymans


class User(UserMixin):
    def __init__(self, username):
        self.id = username


logger = logging.getLogger('heymans')
logging.basicConfig(level=logging.INFO, force=True)
app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = config.flask_secret_key
login_manager = LoginManager()
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)
login_manager.init_app(app)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    message = data['message']
    session_id = data.get('session_id', 'default')
    user_id = current_user.get_id()
    heymans = Heymans(user_id=user_id, persistent=True)
    reply, metadata = heymans.send_user_message(message)
    return jsonify({'response': utils.md(f'{config.ai_name}: {reply}'),
                    'metadata': metadata})
    
    
def clear_message_history():
    user_id = current_user.get_id()
    heymans = Heymans(user_id=user_id, persistent=True)
    heymans.messages.clear()
    heymans.messages.save()
    
    
def chat_page():
    user_id = current_user.get_id()
    heymans = Heymans(user_id=user_id, persistent=True)
    html = ''
    previous_timestamp = None
    previous_answer_model = None
    for role, message, metadata in heymans.messages:
        if role == 'assistant':
            html_body = utils.md(f'{config.ai_name}: {message}')
            html_class = 'message-ai'
        else:
            html_body = '<p>' + utils.clean(f'You: {message}') + '</p>'
            html_class = 'message-user'
        if 'sources' in metadata:
            sources_div = '<div class="message-sources">'
            sources = json.loads(metadata['sources'])
            for source in sources:
                if source['url']:
                    sources_div += f'<a href="{source["url"]}">{source["url"]}</a><br />'
            sources_div += '</div>'
        else:
            sources_div = ''
        if previous_timestamp != metadata['timestamp']:
            previous_timestamp = metadata['timestamp']
            timestamp_div = f'<div class="message-timestamp">{metadata["timestamp"]}</div>'
        else:
            timestamp_div = ''
        if role == 'assistant' and previous_answer_model != metadata['answer_model']:
            previous_answer_model = metadata['answer_model']
            answer_model_div = f'<div class="message-answer-model">{metadata["answer_model"]}</div>'
        else:
            answer_model_div = ''
            
        html += f'<div class="{html_class}">{html_body}{timestamp_div}{answer_model_div}{sources_div}</div>'
    return utils.render('chat.html', message_history=html)


def login_handler(form, html):
    if form.validate_on_submit():
        if not config.validate_user(form.username.data,
                                    form.password.data):
            return redirect('/login_failed')
        user = User(form.username.data)
        login_user(user)
        return redirect('/')
    return utils.render(html, form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    return login_handler(LoginForm(), 'login.html')


@app.route('/login_failed', methods=['GET', 'POST'])
def login_failed():
    return login_handler(LoginForm(), 'login_failed.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')


@app.route('/clear')
def clear():
    clear_message_history()
    return redirect('/chat')


@app.route('/')
def main():
    if current_user.is_authenticated:
        return chat_page()
    return redirect(url_for('login'))
    
@app.route('/chat')
@login_required
def chat():
    return chat_page()


@app.route('/library')
def library():
    return utils.render('library.html')


@app.route('/main.js')
def main_js():
    return utils.render('main.js')

    
@app.route('/stylesheet.css')
def stylesheet():
    return Response(utils.render('stylesheet.css'), mimetype='text/css')
