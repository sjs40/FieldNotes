import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.auth import CurrentUser,get_current_user
from backend.app.database import Base,get_session
from backend.app.main import app
class SprintThreeTests(unittest.TestCase):
 def setUp(self):
  e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);self.s=sessionmaker(bind=e)()
  def override():yield self.s
  app.dependency_overrides[get_session]=override;app.dependency_overrides[get_current_user]=lambda:CurrentUser('u1','u1@test','U');self.c=TestClient(app)
 def tearDown(self):self.c.close();app.dependency_overrides.clear();self.s.close()
 def test_capture_idempotent_source_to_draft_without_call(self):
  p={'channel':'pwa','idempotency_key':'capture-001','item_type':'url','title':'Research','text':'$AAPL #AI','url':'https://EXAMPLE.com/article/'};first=self.c.post('/api/capture',json=p);self.assertEqual(first.status_code,200);second=self.c.post('/api/capture',json=p);self.assertTrue(second.json()['idempotent_replay']);item=first.json()['item'];draft=self.c.post('/api/inbox/'+item['id']+'/create-note');self.assertEqual(draft.status_code,200);self.assertEqual(draft.json().get('calls',[]),[]);self.assertEqual(len(self.c.get('/api/sources').json()),1)
if __name__=='__main__':unittest.main()
