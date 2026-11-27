// Diagnóstico individual: luces/sonido largo. No usar con el puente de la web.
#include <Arduino.h>
const uint8_t DS=5, LATCH=18, CLOCK=19;
const uint32_t DESCANSO_MS=1000;
bool activo=false, descanso=false, invalida=false;
uint32_t inicio=0, duracion=0, fin=0;
uint8_t canal=0;
char linea[24];uint8_t longitud=0;
void escribir(uint16_t bits){
  digitalWrite(LATCH,LOW);
  shiftOut(DS,CLOCK,MSBFIRST,highByte(bits));delayMicroseconds(20);
  shiftOut(DS,CLOCK,MSBFIRST,lowByte(bits));delayMicroseconds(20);
  digitalWrite(LATCH,HIGH);digitalWrite(LATCH,LOW);
}
void parar(){escribir(0);activo=false;descanso=true;fin=millis();}
bool canalSinIdentificar(int n){return n==1||n==5||n==8||n==9||n==11||n==14||n==16;}
void actualizar(){
  if(activo && (uint32_t)(millis()-inicio)>=duracion){
    parar();Serial.println("LIBERADO -> observa si la funcion se activa AL SOLTAR");
  }
  if(descanso && (uint32_t)(millis()-fin)>=DESCANSO_MS)descanso=false;
}
void procesar(){
  char modo=0,extra=0;int n=0;
  if(sscanf(linea,"%c %d %c",&modo,&n,&extra)!=2){parar();Serial.println("Usa C numero, L numero, F numero, o S");return;}
  modo=toupper(modo);
  uint32_t ms=modo=='C'?250:modo=='L'?3000:modo=='F'?5000:0;
  if(!ms||!canalSinIdentificar(n)){
    parar();Serial.println("RECHAZADO: prueba solo canales desconocidos 1,5,8,9,11,14,16");return;
  }
  if(activo||descanso){Serial.println("Espera y vuelve a enviar; no se encolan pruebas");return;}
  canal=n;duracion=ms;inicio=millis();activo=true;
  escribir((uint16_t)(1U<<(n-1)));
  Serial.print("CANAL ");Serial.print(n);Serial.print(" HIGH ");Serial.print(ms);Serial.println(" ms");
}
void setup(){
  pinMode(DS,OUTPUT);pinMode(LATCH,OUTPUT);pinMode(CLOCK,OUTPUT);
  digitalWrite(DS,LOW);digitalWrite(LATCH,LOW);digitalWrite(CLOCK,LOW);escribir(0);
  Serial.begin(115200);
  Serial.println("DIAG-PULSOS/1 - 115200 baudios, Nueva linea");
  Serial.println("C 5 = canal 5 corto 250 ms | L 5 = largo 3 s | F 5 = largo 5 s");
  Serial.println("S = soltar todo YA. Canales permitidos: 1,5,8,9,11,14,16");
  Serial.println("Una prueba manual cada vez. Mantener ruedas libres, sin carga.");
}
void loop(){
  actualizar();
  for(uint8_t i=0;i<32 && Serial.available();++i){
    char c=Serial.read();
    if(c=='S'||c=='s'){parar();longitud=0;invalida=false;Serial.println("STOP: todas LOW");continue;}
    if(c=='\n'||c=='\r'){
      if(!invalida && longitud){linea[longitud]=0;procesar();}
      else if(invalida)Serial.println("Entrada demasiado larga; salidas LOW");
      longitud=0;invalida=false;
    }else if(!invalida){
      if(longitud<sizeof(linea)-1)linea[longitud++]=c;
      else{parar();longitud=0;invalida=true;}
    }
    actualizar();
  }
}
