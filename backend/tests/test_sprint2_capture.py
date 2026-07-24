from datetime import datetime, timezone
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app

class SprintTwoCaptureTests(unittest.TestCase):
 def setUp(self):
  engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);self.s=sessionmaker(bind=engine)();Base.metadata.create_all(engine)
  def override():yield self.s
  app.dependency_overrides[get_session]=override;app.dependency_overrides[get_current_user]=lambda:CurrentUser('u2','u2@test','U2');self.client=TestClient(app)
 def tearDown(self):self.client.close();app.dependency_overrides.clear();self.s.close()
 def test_metric_idea_and_workspaces(self):
  self.assertEqual(self.client.post('/api/metric-cards',json={'metric_name':'Revenue','value':12,'period':'Q2','ticker':'AAPL'}).status_code,200)
  idea=self.client.post('/api/ideas',json={'title':'Pricing power','ticker_symbols':['AAPL']});self.assertEqual(idea.status_code,200);self.assertEqual(self.client.post('/api/ideas/'+idea.json()['id']+'/promote').status_code,200)
  self.assertEqual(self.client.get('/api/workspaces/daily').status_code,200);self.assertEqual(self.client.post('/api/workspaces/weekly',json={}).status_code,200);self.assertEqual(self.client.get('/api/patterns').status_code,200)
 def test_table_chart_and_compound_saved_view(self):
  table=self.client.post('/api/tables/parse',json={'text':'Period|Value\nQ1|10\nQ2|12'});self.assertEqual(table.status_code,200)
  card=self.client.post('/api/metric-cards',json={'metric_name':'Revenue','value':12,'period':'Q2','data':{'points':[{'x':'Q1','y':10},{'x':'Q2','y':12}]}}).json();self.assertEqual(self.client.post('/api/charts',json={'metric_card_id':card['id'],'chart_type':'line'}).status_code,200)
  view=self.client.post('/api/saved-views',json={'name':'Open or critical','resource':'questions','filters':{'or':[{'status':'open'},{'priority':'critical'}]}});self.assertEqual(view.status_code,200);self.assertEqual(self.client.get('/api/saved-views/'+view.json()['id']+'/results').status_code,200)
if __name__=='__main__':unittest.main()
