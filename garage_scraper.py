from flask import Flask,jsonify;import requests;from bs4 import BeautifulSoup;from collections import OrderedDict
app=Flask(__name__)
def get_vehicle_data(r):
 try:v=BeautifulSoup(requests.get(f"https://bookmygarage.com/garage-detail/sussexautocareltd/rh12lw/book/?ref=sussexautocare.co.uk&vrm={r}&referrer=widget",headers={'User-Agent':'Mozilla/5.0'}).text,'html.parser').select_one("div.row.second-header div.col.m9.s12>span>span:nth-child(2)").get_text(strip=True).split(',');c=v[0].replace('-','').strip().split(' ',1);return OrderedDict([('reg',r.upper()),('make',c[0]),('model',c[1]),('fuel',v[1].strip()),('cc',v[2].replace('cc','').strip()),('transmission',v[3].strip())])
 except:return None
@app.route('/test/<r>')
def test_vehicle_lookup(r):return jsonify(get_vehicle_data(r)or{"error":"No data found"})
if __name__=="__main__":app.run(debug=True,host='127.0.0.1',port=5001)
