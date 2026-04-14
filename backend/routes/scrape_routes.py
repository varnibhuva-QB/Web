from flask import Blueprint, request, jsonify
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.google_maps import scrape_google_maps
from scrapers.indiamart import scrape_indiamart
from scrapers.zoho_partner import scrape_zoho_partner
from scrapers.goodfirm import scrape_goodfirm
from models.db import (
    save_leads,
    get_leads,
    test_connection,
    get_user_by_identifier,
    create_user,
    verify_password,
    create_session,
    get_user_by_token,
    update_login_stats,
    update_user_contact,
    update_user_profile,
    change_user_password,
    set_two_step_verification,
    log_scrape_activity,
    get_admin_stats,
)

scrape_bp = Blueprint('scrape', __name__)

SCRAPERS = {
    'google_maps': scrape_google_maps,
    'indiamart': scrape_indiamart,
    'zoho_partner': scrape_zoho_partner,
    'goodfirm': scrape_goodfirm,
}


def get_auth_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    token = request.headers.get('x-auth-token') or request.args.get('auth_token')
    return token


def require_user(db_server, db_name):
    token = get_auth_token()
    user = get_user_by_token(token, db_server, db_name)
    if not user:
        return None
    return user


def require_superadmin(db_server, db_name):
    user = require_user(db_server, db_name)
    if not user or not user.get('is_superadmin'):
        return None
    return user


@scrape_bp.route('/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.json or {}
        identifier = (data.get('email') or data.get('phone') or data.get('identifier') or '').strip()
        password = data.get('password') or ''
        db_server = data.get('db_server', 'ADMIN\\SQLEXPRESS')
        db_name = data.get('db_name', 'leads_db')

        if not identifier or not password:
            return jsonify({"error": "Email/phone and password are required"}), 400

        user = get_user_by_identifier(identifier, db_server, db_name)
        if user:
            if not verify_password(password, user['password_hash']):
                return jsonify({"error": "Invalid credentials"}), 401
        else:
            if '@' in identifier:
                user = create_user(email=identifier, password=password, server=db_server, database=db_name)
            else:
                user = create_user(phone=identifier, password=password, server=db_server, database=db_name)

        token = create_session(user['id'], db_server, db_name)
        update_login_stats(user['id'], db_server, db_name)

        display_name = user.get('display_name') or (user.get('full_name') or '').split()[0] if user.get('full_name') else None
        if not display_name:
            display_name = user.get('email') or user.get('phone')

        profile_required = not bool(user.get('profile_complete'))

        return jsonify({
            "status": "ok",
            "token": token,
            "is_superadmin": user['is_superadmin'],
            "email": user.get('email'),
            "phone": user.get('phone'),
            "display_name": display_name,
            "profile_required": profile_required,
            "full_name": user.get('full_name'),
            "birthdate": user.get('birthdate') and user.get('birthdate').isoformat()
        })
    except Exception as exc:
        return jsonify({"error": f"Auth login failed: {exc}"}), 500


@scrape_bp.route('/auth/me', methods=['GET'])
def auth_me():
    db_server = request.args.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = request.args.get('db_name', 'leads_db')
    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    display_name = user.get('display_name') or (user.get('full_name') or '').split()[0] if user.get('full_name') else None
    if not display_name:
        display_name = user.get('email') or user.get('phone')
    return jsonify({
        'email': user.get('email'),
        'phone': user.get('phone'),
        'is_superadmin': user.get('is_superadmin'),
        'display_name': display_name,
        'full_name': user.get('full_name'),
        'birthdate': user.get('birthdate') and user.get('birthdate').isoformat(),
        'profile_required': not bool(user.get('profile_complete'))
    })


@scrape_bp.route('/auth/profile', methods=['POST'])
def auth_profile():
    db_server = request.json.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = request.json.get('db_name', 'leads_db')
    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    email = (request.json.get('email') or '').strip().lower() or None
    phone = (request.json.get('phone') or '').strip() or None
    full_name = (request.json.get('full_name') or '').strip() or None
    display_name = (request.json.get('display_name') or '').strip() or None
    birthdate = (request.json.get('birthdate') or '').strip() or None

    if not email and not phone and not full_name and not birthdate and not display_name:
        return jsonify({"error": "Email, phone, full name, display name, or birthdate is required"}), 400

    try:
        update_user_profile(
            user['id'],
            email=email,
            phone=phone,
            full_name=full_name,
            birthdate=birthdate,
            display_name=display_name,
            server=db_server,
            database=db_name
        )
        updated_user = get_user_by_token(get_auth_token(), db_server, db_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if not updated_user:
        return jsonify({"status": "ok"})

    display_name = updated_user.get('display_name') or (updated_user.get('full_name') or '').split()[0] if updated_user.get('full_name') else None
    if not display_name:
        display_name = updated_user.get('email') or updated_user.get('phone')

    return jsonify({
        "status": "ok",
        "email": updated_user.get('email'),
        "phone": updated_user.get('phone'),
        "display_name": display_name,
        "full_name": updated_user.get('full_name'),
        "birthdate": updated_user.get('birthdate') and updated_user.get('birthdate').isoformat(),
        "profile_required": not bool(updated_user.get('profile_complete'))
    })


@scrape_bp.route('/auth/password', methods=['POST'])
def auth_password():
    data = request.json or {}
    db_server = data.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = data.get('db_name', 'leads_db')
    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    if not old_password or not new_password:
        return jsonify({"error": "Old and new passwords are required"}), 400

    current_user = get_user_by_identifier(user.get('email') or user.get('phone'), db_server, db_name)
    if not current_user or not verify_password(old_password, current_user['password_hash']):
        return jsonify({"error": "Invalid current password"}), 401

    change_user_password(user['id'], new_password, server=db_server, database=db_name)
    return jsonify({"status": "ok", "message": "Password updated"})


@scrape_bp.route('/auth/two-step', methods=['POST'])
def auth_two_step():
    data = request.json or {}
    db_server = data.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = data.get('db_name', 'leads_db')
    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    enabled = data.get('enabled')
    if enabled is None:
        return jsonify({"error": "Enabled flag is required"}), 400

    set_two_step_verification(user['id'], bool(enabled), server=db_server, database=db_name)
    return jsonify({"status": "ok", "two_step_enabled": bool(enabled)})


@scrape_bp.route('/scrape', methods=['POST', 'OPTIONS'])
def scrape():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.json
    source = data.get('source', 'google_maps')
    keyword = data['keyword']
    location = data['location']
    max_results = data.get('max_results', 10)
    db_server = data.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = data.get('db_name', 'leads_db')

    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    scraper_func = SCRAPERS.get(source)
    if not scraper_func:
        return jsonify({"error": f"Scraper for {source} not found"}), 400

    try:
        result = scraper_func(keyword, location, max_results)
        save_leads(result, source, server=db_server, database=db_name)
        log_scrape_activity(user['id'], source, keyword, location, len(result), db_server, db_name)
        return jsonify({"message": f"Scraped {len(result)} leads from {source}", "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scrape_bp.route('/leads', methods=['GET'])
def get_leads_route():
    source = request.args.get('source')
    limit = int(request.args.get('limit', 100))
    db_server = request.args.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = request.args.get('db_name', 'leads_db')

    user = require_user(db_server, db_name)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    leads = get_leads(source, limit, server=db_server, database=db_name)
    return jsonify(leads)


@scrape_bp.route('/admin/stats', methods=['GET'])
def admin_stats():
    db_server = request.args.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = request.args.get('db_name', 'leads_db')
    user = require_superadmin(db_server, db_name)
    if not user:
        return jsonify({"error": "Admin access required"}), 403

    stats = get_admin_stats(db_server, db_name)
    return jsonify(stats)


@scrape_bp.route('/db-test', methods=['POST'])
def db_test_route():
    data = request.json or {}
    db_server = data.get('db_server', 'ADMIN\\SQLEXPRESS')
    db_name = data.get('db_name', 'leads_db')
    try:
        test_connection(db_server, db_name)
        return jsonify({"status": "ok", "message": "Connection successful"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500