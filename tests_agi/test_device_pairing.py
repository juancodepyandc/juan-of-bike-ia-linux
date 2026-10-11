import hashlib
import json
from flask import Blueprint,Flask,jsonify
import pytest
from application.device_pairing import register_device_routes,device_auth,COOKIE

@pytest.fixture
def app(tmp_path):
    app=Flask(__name__);bp=Blueprint('devices',__name__)
    register_device_routes(bp,tmp_path,local=lambda:not __import__('flask').request.headers.get('X-Forwarded-For'))
    @bp.route('/probe',methods=['GET','POST'])
    def probe():return jsonify(connected=bool(device_auth(tmp_path)))
    app.register_blueprint(bp);return app

PUBLIC={'X-Forwarded-For':'203.0.113.1','Origin':'https://aurora.test'}
LOCAL={'Origin':'http://localhost'}

def pair(app):
    phone=app.test_client();pc=app.test_client()
    result=phone.post('/api/devices/pair',json={'name':'Mon téléphone'},headers=PUBLIC,base_url='https://aurora.test').get_json()
    assert not phone.post('/api/devices/claim',json={'claim':result['claim']},headers=PUBLIC,base_url='https://aurora.test').get_json()['connected']
    assert pc.post('/api/devices/manage',json={'action':'approve','code':result['code']},headers=LOCAL).status_code==200
    response=phone.post('/api/devices/claim',json={'claim':result['claim']},headers=PUBLIC,base_url='https://aurora.test')
    assert response.get_json()['connected'];return phone,pc,result,response

def test_real_approval_secret_cookie_hash_persistence_and_revoke(app,tmp_path):
    phone,pc,pending,response=pair(app)
    cookie=response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=Strict' in cookie
    assert phone.post('/probe',headers=PUBLIC,base_url='https://aurora.test').get_json()['connected']
    assert not phone.post('/probe',headers={**PUBLIC,'Origin':'https://attacker.test'},base_url='https://aurora.test').get_json()['connected']
    assert phone.post('/api/devices/claim',json={'claim':pending['claim']},headers=PUBLIC,base_url='https://aurora.test').status_code==410
    stored=json.loads((tmp_path/'.aurora'/'devices.json').read_text())
    assert pending['claim'] not in json.dumps(stored)
    raw=phone.get_cookie(COOKIE,domain='aurora.test').value
    assert raw not in json.dumps(stored) and stored['devices'][0]['hash']==hashlib.sha256(raw.encode()).hexdigest()
    device=pc.get('/api/devices/manage').get_json()['devices'][0]
    assert 'hash' not in device
    assert pc.post('/api/devices/manage',json={'action':'revoke','id':device['id']},headers=LOCAL).status_code==200
    assert not phone.get('/probe',headers=PUBLIC,base_url='https://aurora.test').get_json()['connected']

def test_public_cannot_approve_or_read_requests_and_local_csrf_blocked(app):
    client=app.test_client()
    assert client.get('/devices',headers=PUBLIC).status_code==403
    assert client.get('/api/devices/manage',headers=PUBLIC).status_code==403
    assert client.post('/api/devices/manage',headers=PUBLIC,json={'action':'approve','code':'123456'}).status_code==403
    assert client.post('/api/devices/manage',headers={'Origin':'https://attacker.test'},json={'action':'approve','code':'123456'}).status_code==403
    assert client.post('/api/devices/manage',json={'action':'approve','code':'123456'}).status_code==403

def test_code_alone_cannot_claim_and_requests_are_limited(app):
    client=app.test_client()
    assert client.post('/api/devices/claim',json={'code':'123456'},headers=PUBLIC).status_code==400
    for i in range(5):assert client.post('/api/devices/pair',json={'name':'Phone'},headers=PUBLIC).status_code==200
    assert client.post('/api/devices/pair',json={'name':'Phone'},headers=PUBLIC).status_code==429
