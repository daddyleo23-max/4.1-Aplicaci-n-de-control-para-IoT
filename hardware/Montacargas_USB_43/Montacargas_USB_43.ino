// ESP32 + 2 x 74HC595 + PC817. Pines del sketch numérico confirmado por el usuario.
// Protocolo USB IOT43/1: no acepta las letras del firmware anterior.
// Sólo sustituye el firmware cuando el cableado y las salidas se hayan comprobado.
#include <Arduino.h>
const uint8_t DS_PIN=5, SHCP_PIN=19, STCP_PIN=18;
// El sketch numérico confirma los pines, pero no identifica qué botón es cada bit.
// No habilitar hasta contrastar los números 1..16 con las funciones físicas.
const bool CHANNEL_MAP_VERIFIED=false;
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
  if(!strcmp(orden,"HELLO")){armado=false;parar();Serial.println("READY IOT43/1");return;}
  if(!strcmp(orden,"DISARM")){armado=false;parar();return;}
  if(!strcmp(orden,"ARM")){parar();armado=true;ultimoHeartbeat=ahora;Serial.println("ARMED");return;}
  if(!armado)return;
  if(!strcmp(orden,"H")){ultimoHeartbeat=ahora;return;}
  if(strncmp(orden,"C ",2)||strlen(orden)!=3)return;
  if(!CHANNEL_MAP_VERIFIED){parar();Serial.println("MAP PENDING: no movement enabled");return;}
  uint16_t mascara=0;bool pulso=false;
  switch(orden[2]){
    case 'W':mascara=1<<0;break;case 'S':mascara=1<<1;break;
    case 'Q':mascara=1<<2;break;case 'E':mascara=1<<3;break;
    case 'A':mascara=1<<9;break;case 'D':mascara=1<<11;break;
    case 'L':mascara=1<<6;pulso=true;break;
    case 'N':mascara=1<<8;pulso=true;break;
    case 'V':mascara=1<<5;pulso=true;break;
    default:parar();return;
  }
  if(pulso){toque=mascara;pulsoActivo=true;finToque=ahora+150;}
  else{movimiento=mascara;inicioMovimiento=ahora;}
  salida();Serial.println("APPLIED"); // Confirma salida GPIO, no desplazamiento físico.
}
void setup(){
  pinMode(DS_PIN,OUTPUT);pinMode(SHCP_PIN,OUTPUT);pinMode(STCP_PIN,OUTPUT);
  digitalWrite(DS_PIN,LOW);digitalWrite(SHCP_PIN,LOW);digitalWrite(STCP_PIN,LOW);
  parar();Serial.begin(115200);Serial.println("READY IOT43/1");
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
