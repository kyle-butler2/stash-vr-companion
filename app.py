import random
from flask import Flask,jsonify,render_template,request,Response,redirect,session, url_for
import requests
import json
import os
import datetime
from pathlib import Path


app = Flask(__name__)

#app.config['SERVER_NAME'] = 'http://deovr.home'
app.config['GRAPHQL_API'] = os.getenv('API_URL', 'http://localhost:9999/graphql')

app.secret_key = 'N46XYWbnaXG6JtdJZxez'


headers = {
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Connection": "keep-alive",
    "DNT": "1"
}
if os.getenv('API_KEY'):
    headers['ApiKey']=os.getenv('API_KEY')

studios=[]
performers=[]
tags_filters={}
tags_cache={}
viewed_scene_ids=[]


def __callGraphQL(query, variables=None):
    json = {}
    json['query'] = query
    if variables != None:
        json['variables'] = variables

    # handle cookies
    response = requests.post(app.config['GRAPHQL_API'], json=json, headers=headers)

    if response.status_code == 200:
        result = response.json()
        if result.get("error", None):
            for error in result["error"]["errors"]:
                raise Exception("GraphQL error: {}".format(error))
        if result.get("data", None):
            return result.get("data")
    else:
        raise Exception(
            "GraphQL query failed:{} - {}. Query: {}. Variables: {}".format(response.status_code, response.content,
                                                                            query, variables))

def get_scenes():
    query = """
query findScenes($export_deovr_tag_id: ID!) {
findScenes(scene_filter: {tags: {depth: 0, modifier: INCLUDES_ALL, value: [$export_deovr_tag_id]}}, filter: {sort: "file_mod_time",direction: DESC,per_page: -1} ) {
count
scenes {
  id
  checksum
  oshash
  title
  details
  url
  date
  rating
  organized
  o_counter
  path
  interactive
  file {
    size
    duration
    video_codec
    audio_codec
    width
    height
    framerate
    bitrate
  }
  paths {
    screenshot
    preview
    stream
    webp
    vtt
    chapters_vtt
    sprite
    funscript
  }
  galleries {
    id
    checksum
    path
    title
    url
    date
    details
    rating
    organized
    studio {
      id
      name
      url
    }
    image_count
    tags {
      id
      name
      image_path
      scene_count
    }
  }
  performers {
    id
    name
    gender
    url
    twitter
    instagram
    birthdate
    ethnicity
    country
    eye_color
    country
    height
    measurements
    fake_tits
    career_length
    tattoos
    piercings
    aliases
  }
  studio{
    id
    name
    url
    stash_ids{
      endpoint
      stash_id
    }
  }
tags{
    id
    name
  }

  stash_ids{
    endpoint
    stash_id
  }
}
}
}"""


    variables = {"export_deovr_tag_id": tags_cache["export_deovr"]["id"]}
    result = __callGraphQL(query, variables)
    res= result["findScenes"]["scenes"]
    for s in res:
        scene_type(s)
        if 'ApiKey' in headers:
            rewrite_image_url(s)
    return res


def lookupScene(id):
    query = """query findScene($scene_id: ID!){
findScene(id: $scene_id){
  id
  checksum
  oshash
  title
  details
  url
  date
  rating
  organized
  o_counter
  path
  interactive
  file {
    size
    duration
    video_codec
    audio_codec
    width
    height
    framerate
    bitrate
  }
  paths {
    screenshot
    preview
    stream
    webp
    vtt
    chapters_vtt
    sprite
    funscript
  }
  galleries {
    id
    checksum
    path
    title
    url
    date
    details
    rating
    organized
    studio {
      id
      name
      url
    }
    image_count
    tags {
      id
      name
      image_path
      scene_count
    }
  }
  performers {
    id
    name
    gender
    url
    twitter
    instagram
    birthdate
    ethnicity
    country
    eye_color
    country
    height
    measurements
    fake_tits
    career_length
    tattoos
    piercings
    aliases
  }
  studio{
    id
    name
    url
    stash_ids{
      endpoint
      stash_id
    }
  }
  scene_markers{
    seconds
    title
    primary_tag{
      name
    }
  }
tags{
    id
    name
  }

  stash_ids{
    endpoint
    stash_id
  }
}
}"""
    variables = {"scene_id": id}
    result = __callGraphQL(query, variables)
    res= result["findScene"]
    scene_type(res)
    if 'ApiKey' in headers:
        rewrite_image_url(res)
    return res

def findTagIdWithName(name):
    query = """query {
allTags {
id
name
}
}"""

    result = __callGraphQL(query)

    for tag in result["allTags"]:
        if tag["name"] == name:
            return tag["id"]
    return None

def findPerformerIdWithName(name):
    query = """query {
  allPerformers {
    id
    name
  }
}"""
    result = __callGraphQL(query)
    for tag in result["allPerformers"]:
        if tag["name"] == name:
            return tag["id"]
    return None


def findPerformerWithID(id):
    query = """query findPerformer($performer_id: ID!){
  findPerformer(id: $performer_id){
    id
    name
    gender
    url
    twitter
    instagram
    birthdate
    ethnicity
    country
    eye_color
    country
    height
    measurements
    fake_tits
    career_length
    tattoos
    piercings
    aliases
    image_path
    tags{
      id
      name
    }
  }
}"""
    variables = {"performer_id": id}
    result = __callGraphQL(query, variables)
    return result['findPerformer']



def findStudioIdWithName(name):
    query = """query {
  allStudios {
    id
    name
  }
}"""
    result = __callGraphQL(query)
    for tag in result["allStudios"]:
        if tag["name"] == name:
            return tag["id"]
    return None


def build_studio_filters():
    query = """query {
      allStudios {
        id
        name
        details
      }
    }"""
    result = __callGraphQL(query)
    res=[]
    for s in result["allStudios"]:
        if s['details'] is not None and 'EXPORT_DEOVR' in s['details']:
            if s['name'] not in studios:
                studio_fiter={}
                studio_fiter['name']=s['name']
                studio_fiter['type']='STUDIO'
                studio_fiter['studio_id']=s['id']
#                studio_fiter['filter']={
#                    "tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [tags_cache['export_deovr']['id']]},
#                    "studios": {"depth": 3, "modifier": "INCLUDES_ALL", "value": [s['id']]}}
                studio_fiter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
                studio_fiter['post']=tag_cleanup_studio
                res.append(studio_fiter)
    return res

def build_performer_filters():
    query = """{
  allPerformers{
  id
  name
  tags{
    id
    name
  }
}}"""
    result = __callGraphQL(query)
    res=[]
    for p in result["allPerformers"]:
        for tag in p['tags']:
            if tag["name"] == 'export_deovr':
                if p['name'] not in performers:
                    performer_filter = {
                        'name': p['name'],
                        'type': 'PERFORMER',
                        'performer_id': p['id'],
                        'post': tag_cleanup_performer
                    }
                    res.append(performer_filter)
    return res

def build_tag_filters():
    res=[]
    for f in tags_cache['export_deovr']['children']:
        tags_filter_vr={}
        tags_filter_vr['name']="VR " + f['name']
        tags_filter_vr['type']='TAG'
        tags_filter_vr['id']=f['id']
        tags_filter_vr['post']=[random_sort, tag_cleanup, tag_cleanup_3d]
        tags_filter_2d = tags_filter_vr.copy()
        tags_filter_2d['name']= "2D " + f['name']
        tags_filter_2d['post']=[random_sort, tag_cleanup, tag_cleanup_2d]
        res.append(tags_filter_vr)
        res.append(tags_filter_2d)
    return res

def tag_cleanup(scenes,filter):
    res=[]
    for s in scenes:
        if filter['id'] in [x['id']  for x in s['tags']]:
            res.append(s)
    return res

def tag_cleanup_3d(scenes, _):
    res=[]
    for s in scenes:
        if s["is3d"]:
            res.append(s)
    return res

def tag_cleanup_2d(scenes, _):
    res=[]
    for s in scenes:
        if not s["is3d"]:
            res.append(s)
    return res

def random_sort(scenes, _):
    random.shuffle(scenes)
    return scenes


def tag_cleanup_star(scenes, _):
    res=[]
    for s in scenes:
        if s["rating"]==5:
            res.append(s)
    return res

def tag_cleanup_studio(scenes, _):
    res=[]
    for s in scenes:
        if s["studio"] is not None and 'id' in s['studio']:
            if filter['studio_id'] == s['studio']['id']:
                res.append(s)
    return res

def tag_cleanup_performer(scenes, filter):
    res=[]
    for s in scenes:
        if filter['performer_id'] in [x['id'] for x in s['performers']]:
            res.append(s)
    return res

def only_unspewed(scenes, _):
    return filter(lambda scene: int(scene['o_counter']) == 0, scenes)

def scene_type(scene):
    if "180_180x180_3dh_LR" in scene["path"]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
        scene["stereoMode"] = "sbs"
    else:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    if 'SBS' in [x["name"] for x in scene["tags"]]:
        scene["stereoMode"] = "sbs"
    elif 'TB' in [x["name"] for x in scene["tags"]]:
        scene["stereoMode"] = "tb"

    if 'FLAT' in [x["name"] for x in scene["tags"]]:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    elif 'DOME' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
    elif 'SPHERE' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "sphere"
    elif 'FISHEYE' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "fisheye"
    elif 'MKX200' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"


def reload_tags():
    query = """{
  allTags{
    id
    name
    children{
     id
      name
    }
  }
}"""
    result = __callGraphQL(query)
    if 'allTags' in result:
        tags_cache.clear()
    for t in result["allTags"]:
        tags_cache[t['name']]=t


def performer_update(self,performer):
    query="""
mutation performerUpdate($input: PerformerUpdateInput!) {
performerUpdate(input: $input) {
id
checksum
name
url
gender
twitter
instagram
birthdate
ethnicity
country
eye_color
height
measurements
fake_tits
career_length
tattoos
piercings
aliases
favorite
image_path
scene_count
stash_ids {
  endpoint
  stash_id
}
}
}
"""
    variables = {'input': performer}
    return self.__callGraphQL(query, variables)


def createTagWithName(name):
    query = """
mutation tagCreate($input:TagCreateInput!) {
tagCreate(input: $input){
id       
}
}
"""
    variables = {'input': {
        'name': name
    }}

    result = __callGraphQL(query, variables)
    return result["tagCreate"]["id"]

def recently_viewed_post(scenes, scene_category):
    id_to_scene = {scene['id']: scene for scene in scenes}
    recent_scenes = []
    for scene_id in viewed_scene_ids:
        recent_scene = id_to_scene.get(scene_id)
        if recent_scene:
            recent_scenes.append(recent_scene)
    
    return recent_scenes


def build_scene_filters():
    reload_tags()

    recent_filter={}
    recent_filter['name']='Recent'
    recent_filter['type']='BUILTIN'

    history_filter = {
        'name': 'History',
        'type': 'BUILTIN',
        'post': recently_viewed_post
    }

    vr_filter ={}
    vr_filter['name']='VR'
    vr_filter['post']=tag_cleanup_3d
    vr_filter['type'] = 'BUILTIN'

    vr_random_filter = {
        'name': 'VR Random',
        'post': [random_sort, tag_cleanup_3d],
        'type': 'BUILTIN'
    }

    vr_unspewed_filter = {
        'name': 'VR Unspewed',
        'post': [random_sort, tag_cleanup_3d, only_unspewed],
        'type': 'BUILTIN'
    }

    flat_filter={}
    flat_filter['name']='2D'
    flat_filter['post']=tag_cleanup_2d
    flat_filter['type'] = 'BUILTIN'

    flat_random_filter = {
        'name': '2D Random',
        'post': [random_sort, tag_cleanup_2d],
        'type': 'BUILTIN'
    }

    flat_unspewed_filter = {
        'name': '2D Unspewed',
        'post': [random_sort, tag_cleanup_2d, only_unspewed],
        'type': 'BUILTIN'
    }

    star_filter={}
    star_filter['name']='5 Star'
    star_filter['post']=tag_cleanup_star
    star_filter['type'] = 'BUILTIN'

    female_pov_filter = {
        'name': 'FPOV',
        'filter': {"tags": {"value": [tags_cache['FPOV']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},
        'type': 'BUILTIN',
        'post':tag_cleanup_3d
    }

    filter=[recent_filter,history_filter,vr_filter,vr_unspewed_filter,vr_random_filter,flat_filter,flat_unspewed_filter,flat_random_filter,star_filter,female_pov_filter]

    filter += build_studio_filters()
    filter += build_performer_filters()
    filter += build_tag_filters()
    return filter

def rewrite_image_url(scene):
    screenshot_url=scene["paths"]["screenshot"]
    scene["paths"]["screenshot"]= url_for('image_proxy', _external=True) + '?scene_id='+screenshot_url.split('/')[4]+'&session_id='+screenshot_url.split('/')[5][11:]

def rewrite_stream_url(scene):
    pass


def setup():
    tags = ["VR", "SBS", "TB", "export_deovr", "FLAT", "DOME", "SPHERE", "FISHEYE", "MKX200"]
    reload_tags()
    for t in tags:
        if t not in tags_cache.keys():
            print("creating tag " +t)
            createTagWithName(t)



@app.route('/deovr',methods=['GET', 'POST'])
def deovr():
    data = {}
    data["authorized"]="1"
    data["scenes"] = []
    all_stash_scenes = get_scenes()

    for scene_category in build_scene_filters():
        # make a copy because the filters are destructive but and I don't want to re-fetch from stash for each.
        scenes = all_stash_scenes[:]
        post_process_functions = scene_category.get('post', [])
        if callable(post_process_functions):
            post_process_functions = [post_process_functions]
        for post_process_function in post_process_functions:
            scenes = post_process_function(scenes, scene_category)
        res = []
        for s in scenes:
            r = {}
            r["title"] = s["title"]
            r["videoLength"] = int(s["file"]["duration"])
            r["thumbnailUrl"] = s["paths"]["screenshot"]
            r["video_url"] = request.base_url + '/' + s["id"]
            res.append(r)
        data["scenes"].append({"name": scene_category['name'], "list": res})
    return jsonify(data)



@app.route('/deovr/<int:scene_id>')
def show_post(scene_id):
    s = lookupScene(scene_id)

    scene = {}
    scene["id"] = s["id"]
    scene["title"] = s["title"]
    scene["authorized"] = 1
    scene["description"] = s["details"]
    scene["thumbnailUrl"] = s["paths"]["screenshot"]
    scene["isFavorite"] = False
    scene["isWatchlist"] = False
    scene["videoLength"] = round(s["file"]["duration"])

    vs = {}
    vs["resolution"] = s["file"]["height"]
    vs["height"] = s["file"]["height"]
    vs["width"] = s["file"]["width"]
    vs["size"] = s["file"]["size"]
    vs["url"] = s["paths"]["stream"]
    scene["encodings"] = [{"name": s["file"]["video_codec"], "videoSources": [vs]}]

    if "is3d" in s:
        scene["is3d"] = s["is3d"]
    if "screenType" in s:   
        scene["screenType"] = s["screenType"]
    if "stereoMode" in s:
        scene["stereoMode"] = s["stereoMode"]

    timeStamps = []
    for m in s["scene_markers"]:
        title = m.get("title", "")
        primary_tag_name =  m.get("primary_tag", {}).get("name", "")
        name = " - ".join([val for val in [primary_tag_name, title] if val])
        timeStamps.append({"ts": m["seconds"], "name": name})
    scene["timeStamps"] = timeStamps

    actors = []
    for p in s["performers"]:
        # actors.append({"id":p["id"],"name":p["name"]})
        actors.append({"id": p["id"], "name": p["name"]})
    scene["actors"] = actors

    scene["fullVideoReady"] = True
    scene["fullAccess"] = True

    if s["interactive"]:
        scene["isScripted"] = True
        scene["fleshlight"]=[{"title": Path(s['path']).stem +'.funscript',"url": s["paths"]["funscript"]}]
    else:
        scene["isScripted"] = False
    
    try:
        viewed_scene_ids.remove(scene['id'])
    except:
        pass
    
    viewed_scene_ids.insert(0, scene['id'])
    if len(viewed_scene_ids) > 100:
        viewed_scene_ids.pop()

    return jsonify(scene)


@app.route('/image_proxy')
def image_proxy():
    scene_id = request.args.get('scene_id')
    session_id = request.args.get('session_id')
    url=app.config['GRAPHQL_API'][:-8]+'/scene/'+scene_id+'/screenshot?'+session_id
    r = requests.get(url,headers=headers)
    return Response(r.content,content_type=r.headers['Content-Type'])


@app.route('/')
def index():
    return redirect("/filter/Recent", code=302)

@app.route('/filter/<string:filter_id>')
def show_category(filter_id):
    session['mode']='deovr'
    tags=[]
    filters=build_scene_filters()
    scenes = get_scenes()
    for f in filters:
        if filter_id == f['name']:
            scenes = get_scenes()
            if 'post' in f:
                post_process_functions = f.get('post', [])
                if callable(post_process_functions):
                    post_process_functions = [post_process_functions]
                
                for post_process_function in post_process_functions:
                    scenes = post_process_function(scenes, f)
            session['filter']=f['name']
            return render_template('index.html',filters=filters,filter=f,isGizmovr=False,scenes=scenes)
    return "Error, filter does not exist"

@app.route('/scene/<int:scene_id>')
def scene(scene_id):
    s = lookupScene(scene_id)
    return render_template('scene.html',scene=s,filters=build_scene_filters())

@app.route('/performer/<int:performer_id>')
def performer(performer_id):
    p=findPerformerWithID(performer_id)
    if 'export_deovr' in [x["name"] for x in p["tags"]]:
        p['isPinned']=True
    else:
        p['isPinned' ] = False
    return render_template('performer.html',performer=p,filters=filter())


@app.route('/gizmovr/<string:filter_id>')
def gizmovr_category(filter_id):
    session['mode']='gizmovr'
    tags=[]
    filters=filter()
    for f in filters:
        if filter_id == f['name']:
            scenes = get_scenes(f['filter'])
            if 'post' in f:
                post_process_functions = f.get('post', [])
                if callable(post_process_functions):
                    post_process_functions = [post_process_functions]
                
                for post_process_function in post_process_functions:
                    scenes = post_process_function(scenes, f)
                
            session['filter']=f['name']
            base_path=request.base_url[:-len(request.path)]
            return render_template('gizmovr.html',filters=filters,filter=f,scenes=scenes,isGizmovr=True,base_path=base_path)
    return "Error, filter does not exist"


@app.route('/gizmovr_scene/<int:scene_id>')
def gizmovr_json(scene_id):
    s = lookupScene(scene_id)
    data ={}
    data["apiType"]="GIZMO"
    data["id"]=int(s["id"])
    data["title"] = s["title"]
    sources={"title":str(s["file"]["width"])+"p",
 #            "fps":s["file"]["framerate"],
 #            "size":s["file"]["size"],
 #            "bitrate":s["file"]["bitrate"],
 #            "width":s["file"]["width"],
#             "height": s["file"]["height"],
             "url":s["paths"]["stream"]+'.mp4'}
    data["sources"] = [sources]
#    data["imageThumb"]=s["paths"]["screenshot"]

    angle={}
    if s["is3d"]:
        if s["stereoMode"]=="tb":
            angle["framePacking"]="TB"
        else:
            angle["framePacking"] ="SBS"
        if s["screenType"] == "sphere":
            angle["angle"]="360"
        else:
            angle["angle"] = "180"
    else:
        angle["framePacking"]="NONE"
        angle["angle"]="FLAT"
    data["format"]=angle

    return jsonify(data)

@app.route('/increment_o_counter/<int:scene_id>')
def increment_o_counter(scene_id):

    query = """
mutation incrementOCounter($scene_id: ID!) {
  sceneIncrementO(id: $scene_id)
}"""
    __callGraphQL(query, {'scene_id': scene_id})

    return redirect("/filter/Recent", code=302)

@app.route('/stash-metadata')
def stash_metadata():

    filter = {}
    scenes=get_scenes(filter)
    data = {}
    data["timestamp"] = datetime.datetime.now().isoformat() + "Z"
    data["bundleVersion"] = "1"
    data2 = []
    index = 1

    if scenes is not None:
        for s in scenes:
            index = index + 1
            r = {}
            r["_id"] = str(index)
            r["scene_id"] = s["id"]

            r["title"] = s["title"]
            if "studio" in s:
                if s["studio"]:
                    r["studio"] = s["studio"]["name"]
            if s["is3d"]:
                r["scene_type"]="VR"
            else:
                r["scene_type"]="2D"

            if "screenType" in s:
                r["screenType"] = s["screenType"]
            if "stereoMode" in s:
                r["stereoMode"] = s["stereoMode"]

            r["gallery"] = None
            tags = []
            if "tags" in s:
                for t in s["tags"]:
                    tags.append(t["name"])
            r["tags"] = tags

            performer = []
            if "performers" in s:
                for t in s["performers"]:
                    performer.append(t["name"])
            r["cast"] = performer
            path = s["path"][s["path"].rindex('/') + 1:]
            r["filename"] = [path]
            r["synopsis"] = s["details"]
            r["released"] = s["date"]
            r["homepage_url"] = s["url"]
            r["covers"]=[s["paths"]["screenshot"]]

            data2.append(r)

    data["scenes"] = data2
    return jsonify(data)


setup()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
