import requests
BASE_URL = "http://127.0.0.1:5000"
def login(username, profilepicture, skin):
    response = requests.post(BASE_URL+"/login", json={"username":username,"profilepicture":profilepicture,"skin":skin})

    print(response.json())
    return response.json()["session"]
def matchmake(sessionid):
    response = requests.get(BASE_URL+"/findmatch" , headers={"Authorization": f"Bearer {sessionid}"})
    print(response.json())
matchmake(login("polypenguin2", "poly.png", "default"))