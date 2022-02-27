import random 



query = ('''query findScenes(){
  findScenes(filter: {sort: {''',
f'random{random.randint(0, 999999)}',
'''  }}) {
    scenes {
      id
      title
      organized
    }
  }
};'''
)

