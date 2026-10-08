from functools import wraps

from flask import jsonify, redirect, session, url_for


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)

    return wrapped


def api_login_required(view_func):
    """API callers receive JSON instead of an HTML login redirect."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify(success=False, error='unauthorized', message='请先登录'), 401
        return view_func(*args, **kwargs)

    return wrapped
