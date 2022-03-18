from multiprocessing import shared_memory
import sysv_ipc
import time
import random
import os
import signal
 
MSG_GAME = 128 #msg queue 1 entre game et joueur
TYPE_TRANSPORT = ["airplane","boat", "car","train","bike","skate","shoes"] #liste des transports ordonée par valeur points du croissante
NB_TRANSPORT = len(TYPE_TRANSPORT)
MSG_JEJOUE = "JEJOUE"
MSG_ENDGAME = "ENDGAME"
TEMPS_ATTENTE = 15
LIST_PID = []
#Creation SHM
# sera crée apres qu'on connait le nb de joueurs
# Joueur               1 2 3 ...
# Offre (1,2 ou 3)     _ _ _ ...
# Busy (0 ou 1)        _ _ _ ...
# Buzzer (no joueur)   _
SHM_NAME = "shm_game"
NB_CARTE_PAR_JOUEUR = 5
shm_game=[]
 
def AfficherBusy(NbJoueur):
    busy = "Etats Busy: "
    for i in range(0,NbJoueur):
        busy+= str(shm_game[NbJoueur+i]) + " "
    print(busy)
 
# on attend que des joueurs se connectent sur MSG QUEUE et on leur renvoit leur no de joueur
def AttenteJoueur():
  global mqgame
  global LIST_PID

  NbJoueur = 0
  print("Game démarrée")
  mqgame = sysv_ipc.MessageQueue(MSG_GAME, sysv_ipc.IPC_CREAT)
  temps = 0
  #on attend 7 joueurs max ou bien 30 s max a condition qu il y ait au moins 2 joueurs
  while NbJoueur <= NB_TRANSPORT and ((temps<TEMPS_ATTENTE) or (temps>=TEMPS_ATTENTE and NbJoueur<=1)):
    try:
      message, t = mqgame.receive(block=False) #rajout du block =False  car receive bloquant par defaut
      if message != "": 
        value = message.decode()
        #print('msg recu  ',value)
        if MSG_JEJOUE in value:
          PID = value[len(MSG_JEJOUE):len(value)]
          
          LIST_PID.append(PID)
          print(LIST_PID)
          
          NbJoueur += 1
          print('le joueur n° :', NbJoueur, "s'est connecté.")
          nojoueur = str(NbJoueur)
          message = nojoueur.encode()
          mqgame.send(message, type=12)
    except sysv_ipc.BusyError as err:
      pass
 
    if ((temps % 5==0) & (TEMPS_ATTENTE-temps > -1)):
      print("En attente de connexion de joueurs ...")
      print("Temps restant avant début de partie : ", TEMPS_ATTENTE - temps, ' secondes')
    if (TEMPS_ATTENTE-temps == 1):
      print('Attachez vos ceintures, le jeu commence !')

    time.sleep(1)
    temps += 1
  print(LIST_PID)
  return NbJoueur
 
def DistributionCartes(NbJoueur):
  #choix des transports utilisés
  #prendre au hasard NbJoueur elmt de la liste allant de 0 à len(transports) (nbtransport)
  
  print("Distribution des cartes, promis ce n'est pas truqué")
  choix_transport = random.sample(list(range(NB_TRANSPORT)), int(NbJoueur))
  #print("choix transport:", choix_transport)
  choix_possible = [] #on construit la liste des choix possibles ordonnée
  for i in range(0, NB_CARTE_PAR_JOUEUR):
    for val in choix_transport:  #on ajoute indice choix transport
      choix_possible.append(val)
  #print("choix possibles:", choix_possible)
  random.shuffle(choix_possible) #on melange
  #print("choix possibles melangés:", choix_possible)
  message = ""
 
  #enoie des cartes aux joueurs 
  for i, choix in enumerate(choix_possible):
    #print("i=",i," choix=",choix)
    message += str(choix)
    if (i % NB_CARTE_PAR_JOUEUR) == (NB_CARTE_PAR_JOUEUR-1): #car i part de 0 donc on arrive a 4 modulo 5
      nojoueur = (i//NB_CARTE_PAR_JOUEUR)+1
      #print("envoi joueur ",nojoueur," Cartes: ",message)
      message = message.encode()
      mqgame.send(message,type=nojoueur+1)
      message = ""  


def game():
  global shm_game
  global tmp_shm_cartes
 
  #Attente joueurs durant 30s
  NbJoueur = AttenteJoueur()
  print("C'est parti avec ",NbJoueur," joueurs")
 
  shm = [0]*(NbJoueur*2+1)  
  shm_game = shared_memory.ShareableList(shm, name=SHM_NAME)
 
  DistributionCartes(NbJoueur)
 
  #print(shm_game)
 
  temps = 0
  while True: #attente gagnant
    gagnant = shm_game[NbJoueur *2] #recupere valeur du buzzer
    if gagnant != 0:
      print("Le gagnant est le joueur : ", gagnant )
      #echange avec le gagnant (on lui envoie "fin de jeu" et on recoit ses cartes et on lui envoie ses points)
      message, t = mqgame.receive(type=1) #att de recevoir cartes du gagnant type=1
      value = message.decode()
      points = 0
      for carte in value:
        points += int(carte)
      print("cartes recues, calcul points ok: ", points)
 
      for i in range(0,NbJoueur):
        # a tous les joueurs on envoie fin de partie et le nom du gagnant avec nb de points
          message = MSG_ENDGAME + str(gagnant) + str(points) #et le gagnant est...
          #print("msg fin=", message)
          message = message.encode()
          mqgame.send(message,type=i+1+1)
      
      print("FIN DE LA PARTIE")
      
      shm_game.shm.close()
      shm_game.shm.unlink()
      mqgame.remove()
      
      for pid in LIST_PID:
        os.kill(int(pid), signal.SIGTERM)
      
      time.sleep(1)

      os.kill(os.getpid(),signal.SIGKILL)
      #suicide du game
   
    if temps % 10==0: #tt les   10 s
      print("Attente d'un gagnant ...")
      AfficherBusy(NbJoueur)
    temps += 1
    time.sleep(1)
 

 
if __name__ == "__main__":
  #signal.signal(signal.SIGINT, handler)
  game()
  