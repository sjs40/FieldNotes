from datetime import datetime, timedelta, timezone
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.journal import create_note
from backend.app.main import app
from backend.app.market_data import Quote
from backend.app.models import CallExpectation, ThesisReview, TrackedCall
from backend.app.parser import parse_note

class SprintTwoTests(unittest.TestCase):
 def setUp(self):
  engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine);self.s=sessionmaker(bind=engine)()
  at=datetime.now(timezone.utc)-timedelta(days=100);create_note(self.s,user_id='u1',parsed=parse_note('$AAPL @bull $300 @target','thesis'),title='Apple thesis',status='published',quotes={'AAPL':Quote('AAPL',200,at,'test'),'SPY':Quote('SPY',500,at,'test')});self.s.commit();self.call=self.s.scalar(select(TrackedCall));self.call.opened_at=at;self.s.commit()
  def session_override(): yield self.s
  app.dependency_overrides[get_session]=session_override;app.dependency_overrides[get_current_user]=lambda:CurrentUser('u1','u1@example.test','U1');self.client=TestClient(app)
 def tearDown(self): self.client.close();app.dependency_overrides.clear();self.s.close()
 def test_stale_generation_is_idempotent(self):
  self.assertGreaterEqual(self.client.post('/api/reviews/generate').json()['created'],1);self.assertEqual(self.client.post('/api/reviews/generate').json()['created'],0)
  review=self.s.scalar(select(ThesisReview).where(ThesisReview.review_type=='stale'));self.assertEqual(review.metadata_json['severity'],'critical')
 def test_snooze_complete_and_isolation(self):
  self.client.post('/api/reviews/generate');review=self.s.scalar(select(ThesisReview));future=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
  self.assertEqual(self.client.post(f'/api/reviews/{review.id}/snooze',json={'snooze_until':future}).status_code,200)
  self.assertEqual(self.client.post(f'/api/reviews/{review.id}/complete',json={'outcome':'maintain','explanation':'Still valid'}).status_code,200)
  self.assertEqual(self.client.get(f'/api/reviews/{review.id}').json()['status'],'completed')
 def test_target_horizon_and_timeline(self):
  expectation=self.s.scalar(select(CallExpectation));expectation.time_horizon_days=30;expectation.catalyst_at=datetime.now(timezone.utc)-timedelta(days=1);self.s.commit()
  self.client.post('/api/reviews/generate');types={r.review_type for r in self.s.scalars(select(ThesisReview)).all()};self.assertIn('horizon',types);self.assertIn('catalyst_due',types)
  timeline=self.client.get('/api/tickers/AAPL/timeline').json();self.assertTrue(any(x['type']=='call_opened' for x in timeline));evolution=self.client.get('/api/tickers/AAPL/thinking-evolution').json();self.assertIn('empty',evolution)
if __name__=='__main__': unittest.main()
