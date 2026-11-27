// ESP32 + 2 x 74HC595 + PC817. Pines del sketch numérico confirmado por el usuario.
// Protocolo USB IOT43/4: no acepta las letras del firmware anterior.
// Sólo sustituye el firmware cuando el cableado y las salidas se hayan comprobado.
#include <Arduino.h>
const uint8_t DS_PIN=5, SHCP_PIN=19, STCP_PIN=18;
// Numeración del diagnóstico = bit + 1; sólo funciones identificadas por el usuario.
const uint8_t BIT_ADELANTE=1, BIT_ATRAS=2, BIT_CLAXON=3;
const uint8_t BIT_SUBIR=6, BIT_IZQUIERDA=11, BIT_DERECHA=12, BIT_BAJAR=14;
// Corrección del usuario: canal 12=izquierda, canal 13=derecha.
// Canal 6: posible velocidad; canal 10: demo autónoma. Ambos deshabilitados.
const uint32_t CLAXON_MS=250, DESCANSO_CLAXON_MS=1000;
uint32_t ultimoClaxon=0;
bool claxonProbado=false;
const uint32_t WATCHDOG_MS=800, RENOVACION_MOVIMIENTO_MS=900;
uint16_t movimiento=0, toque=0;
uint32_t ultimoHeartbeat=0, inicioMovimiento=0, finToque=0, duracionMovimiento=0;
bool movimientoManual=false;
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
void parar(){movimiento=toque=0;pulsoActivo=false;movimientoManual=false;salida();}
void procesar(const char* orden){
  uint32_t ahora=millis();
  if(!strcmp(orden,"X")){parar();Serial.println("STOP");return;}
  if(!strcmp(orden,"HELLO")){armado=false;parar();Serial.println("READY IOT43/4");return;}
  if(!strcmp(orden,"DISARM")){armado=false;parar();return;}
  if(!strcmp(orden,"ARM")){parar();armado=true;ultimoHeartbeat=ahora;Serial.println("ARMED");return;}
  if(!armado)return;
  if(!strcmp(orden,"H")){ultimoHeartbeat=ahora;return;}
  if(!strcmp(orden,"R")){
    if(movimiento && movimientoManual)inicioMovimiento=ahora;
    return;
  }
  if(strncmp(orden,"C ",2))return;
  char letra=0, extra=0; unsigned long duracion=0;
  if(sscanf(orden,"C %c %lu %c",&letra,&duracion,&extra)!=2 || duracion>10000){parar();return;}
  uint16_t mascara=0;
  switch(letra){
    case 'W':mascara=(uint16_t)(1U<<BIT_ADELANTE);break;
    case 'S':mascara=(uint16_t)(1U<<BIT_ATRAS);break;
    case 'A':mascara=(uint16_t)(1U<<BIT_IZQUIERDA);break;
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
  movimientoManual=(duracion==0);
  duracionMovimiento=movimientoManual?RENOVACION_MOVIMIENTO_MS:duracion;
  salida();Serial.println("APPLIED"); // Confirma salida GPIO, no desplazamiento físico.
}
void setup(){
  pinMode(DS_PIN,OUTPUT);pinMode(SHCP_PIN,OUTPUT);pinMode(STCP_PIN,OUTPUT);
  digitalWrite(DS_PIN,LOW);digitalWrite(SHCP_PIN,LOW);digitalWrite(STCP_PIN,LOW);
  parar();Serial.begin(115200);Serial.println("READY IOT43/4");
}
void loop(){
  uint32_t ahora=millis();
  if(armado && ahora-ultimoHeartbeat>WATCHDOG_MS){parar();armado=false;Serial.println("WATCHDOG STOP");}
  if(movimiento && (uint32_t)(ahora-inicioMovimiento)>=duracionMovimiento){
    bool manual=movimientoManual;parar();Serial.println(manual?"LEASE STOP":"STEP STOP");
  }
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
