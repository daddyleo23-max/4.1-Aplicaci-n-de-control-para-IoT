// ESP32 + 2 x 74HC595 + PC817. Pines del sketch numérico confirmado por el usuario.
// Protocolo USB IOT43/2: no acepta las letras del firmware anterior.
// Sólo sustituye el firmware cuando el cableado y las salidas se hayan comprobado.
#include <Arduino.h>
const uint8_t DS_PIN=5, SHCP_PIN=19, STCP_PIN=18;
// Numeración del diagnóstico = bit + 1; sólo funciones identificadas por el usuario.
const uint8_t BIT_ADELANTE=1, BIT_ATRAS=2, BIT_CLAXON=3;
const uint8_t BIT_SUBIR=6, BIT_DERECHA=11, BIT_BAJAR=14;
// Canal 13/bit12 podría ser izquierda, pendiente de confirmar: deshabilitado.
const uint32_t CLAXON_MS=250, DESCANSO_CLAXON_MS=1000;
uint32_t ultimoClaxon=0;
bool claxonProbado=false;
const uint32_t WATCHDOG_MS=800, MAX_MOVIMIENTO_MS=1000;
uint16_t movimiento=0, toque=0;
uint32_t ultimoHeartbeat=0, inicioMovimiento=0, finToque=0;
bool armado=false, pulsoActivo=false;
char linea[32]; size_t longitud=0;

void salida(){
  uint16_t bits=movimiento|toque;
  digitalWrite(STCP_PIN,LOW);
  shiftOut(DS_PIN,SHCP_PIN,MSBFIRST,bits>>8);
  delayMicroseconds(20);
  shiftOut(DS_PIN,SHCP_PIN,MSBFIRST,bits&255);
  delayMicroseconds(20);
  digitalWrite(STCP_PIN,HIGH);
  digitalWrite(STCP_PIN,LOW);
}
void parar(){movimiento=toque=0;pulsoActivo=false;salida();}
void procesar(const char* orden){
  uint32_t ahora=millis();
  if(!strcmp(orden,"X")){parar();Serial.println("STOP");return;}
  if(!strcmp(orden,"HELLO")){armado=false;parar();Serial.println("READY IOT43/2");return;}
  if(!strcmp(orden,"DISARM")){armado=false;parar();return;}
  if(!strcmp(orden,"ARM")){parar();armado=true;ultimoHeartbeat=ahora;Serial.println("ARMED");return;}
  if(!armado)return;
  if(!strcmp(orden,"H")){ultimoHeartbeat=ahora;return;}
  if(strncmp(orden,"C ",2)||strlen(orden)!=3)return;
  uint16_t mascara=0;
  switch(orden[2]){
    case 'W':mascara=(uint16_t)(1U<<BIT_ADELANTE);break;
    case 'S':mascara=(uint16_t)(1U<<BIT_ATRAS);break;
    case 'D':mascara=(uint16_t)(1U<<BIT_DERECHA);break;
    case 'E':mascara=(uint16_t)(1U<<BIT_SUBIR);break;
    case 'Q':mascara=(uint16_t)(1U<<BIT_BAJAR);break;
    case 'N':
      // Nunca prolongar el toque por repeticiones ni activar la función de apagado.
      if(pulsoActivo || (claxonProbado && (uint32_t)(ahora-ultimoClaxon)<DESCANSO_CLAXON_MS))return;
      toque=(uint16_t)(1U<<BIT_CLAXON);pulsoActivo=true;
      finToque=ahora+CLAXON_MS;ultimoClaxon=ahora;claxonProbado=true;
      salida();Serial.println("APPLIED SHORT HORN");return;
    default:parar();Serial.println("UNVERIFIED CHANNEL: STOP");return;
  }
  movimiento=mascara;inicioMovimiento=ahora;
  salida();Serial.println("APPLIED"); // Confirma salida GPIO, no desplazamiento físico.
}
void setup(){
  pinMode(DS_PIN,OUTPUT);pinMode(SHCP_PIN,OUTPUT);pinMode(STCP_PIN,OUTPUT);
  digitalWrite(DS_PIN,LOW);digitalWrite(SHCP_PIN,LOW);digitalWrite(STCP_PIN,LOW);
  parar();Serial.begin(115200);Serial.println("READY IOT43/2");
}
void loop(){
  uint32_t ahora=millis();
  if(armado && ahora-ultimoHeartbeat>WATCHDOG_MS){parar();armado=false;Serial.println("WATCHDOG STOP");}
  if(movimiento && ahora-inicioMovimiento>MAX_MOVIMIENTO_MS){parar();Serial.println("LIMIT STOP");}
  if(pulsoActivo && (int32_t)(ahora-finToque)>=0){toque=0;pulsoActivo=false;salida();}
  // No usar delay(): STOP y watchdog se atienden también durante los pulsos.
  for(uint8_t i=0;i<64 && Serial.available();i++){
    char c=Serial.read();
    if(c=='\n'){linea[longitud]=0;procesar(linea);longitud=0;}
    else if(c!='\r'){
      if(longitud<sizeof(linea)-1)linea[longitud++]=c;
      else{longitud=0;parar();armado=false;}
    }
  }
}
