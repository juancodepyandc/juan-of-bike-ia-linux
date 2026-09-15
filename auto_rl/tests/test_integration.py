import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from fastapi.testclient import TestClient
from auto_rl.integration import register_routes
from auto_rl.runtime import catalog, validated_record
from auto_rl.serve import app


class IntegrationTests(unittest.TestCase):
    def test_no_model_is_advertised_before_validation(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(catalog(Path(d)),[])
            self.assertIsNone(validated_record('code',Path(d)))

    def test_unknown_model_cannot_silently_use_a_base_model(self):
        with patch('auto_rl.serve.catalog',return_value=[]):
            client=TestClient(app)
            self.assertEqual(client.post('/api/chat',json={'model':'aurora-rl-code:v999','messages':[]}).status_code,404)
            self.assertEqual(client.get('/api/tags').json(),{'models':[]})

    def test_bridge_routes_only_the_inference_allowlist(self):
        flask=Flask(__name__);urls=[]
        def proxy(url):urls.append(url);return {'ok':True}
        register_routes(flask,proxy)
        client=flask.test_client()
        self.assertEqual(client.post('/proxy/trained/api/chat',json={}).status_code,200)
        self.assertEqual(urls,['http://127.0.0.1:11435/api/chat'])
        self.assertEqual(client.post('/proxy/trained/api/delete',json={}).status_code,404)
        self.assertEqual(len(urls),1)

    def test_image_workflow_endpoint_preserves_base_without_champion(self):
        flask=Flask(__name__);register_routes(flask,lambda url:{'ok':True})
        client=flask.test_client()
        self.assertEqual(client.post('/api/training/image-workflow',json={}).status_code,400)
        with patch('auto_rl.image_runtime.validated_record',return_value=None):
            graph={'12':{'class_type':'UnetLoaderGGUF','inputs':{'unet_name':'flux.gguf'}}}
            response=client.post('/api/training/image-workflow',json={'workflow':graph})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json,{'workflow':graph})

if __name__=='__main__':unittest.main()
