/*
 * Diagnóstico manual ESP32 + 2 x 74HC595 + optoacopladores.
 * Pines y escritura tomados del sketch numérico comprobado por el usuario.
 * Monitor serie: 115200, Nueva línea o Ambos NL/CR.
 * 1..16 + Enter: un solo canal en HIGH durante 250 ms; resto en LOW.
 * S: todas las salidas LOW inmediatamente (no necesita Enter).
 * Sin barrido automático, sin "todos HIGH", sin conexión con la web.
 */
#include <Arduino.h>

const uint8_t PIN_DS = 5;
const uint8_t PIN_STCP = 18;  // latch
const uint8_t PIN_SHCP = 19;  // reloj
const uint32_t PULSO_MS = 250;
const uint32_t DESCANSO_MS = 500;

char numero[3] = {0};
uint8_t longitud = 0;
bool lineaInvalida = false;
bool pulsoActivo = false;
bool descansoActivo = false;
uint32_t inicioPulso = 0;
uint32_t inicioDescanso = 0;
uint8_t canalActivo = 0;

void escribir16(uint16_t datos) {
  digitalWrite(PIN_STCP, LOW);
  shiftOut(PIN_DS, PIN_SHCP, MSBFIRST, highByte(datos));
  delayMicroseconds(20);
  shiftOut(PIN_DS, PIN_SHCP, MSBFIRST, lowByte(datos));
  delayMicroseconds(20);
  digitalWrite(PIN_STCP, HIGH);
  digitalWrite(PIN_STCP, LOW);
}

void detener() {
  escribir16(0x0000);
  pulsoActivo = false;
  canalActivo = 0;
  inicioDescanso = millis();
  descansoActivo = true;
}

void actualizarPulso() {
  uint32_t ahora = millis();
  if (pulsoActivo && (uint32_t)(ahora - inicioPulso) >= PULSO_MS) {
    uint8_t terminado = canalActivo;
    detener();
    Serial.print(F("FIN canal "));
    Serial.print(terminado);
    Serial.println(F(" -> todas las salidas LOW"));
  }
  if (descansoActivo && (uint32_t)(ahora - inicioDescanso) >= DESCANSO_MS) {
    descansoActivo = false;
  }
}

void probar(uint8_t canal) {
  actualizarPulso();
  if (canal < 1 || canal > 16) {
    detener();
    Serial.println(F("Numero valido: 1..16. Salidas LOW."));
    return;
  }
  if (pulsoActivo || descansoActivo) {
    // Nunca encolar otra salida ni ejecutarla mas tarde.
    Serial.println(F("Espera a que termine el pulso y vuelve a enviar el numero."));
    return;
  }
  canalActivo = canal;
  inicioPulso = millis();
  pulsoActivo = true;
  escribir16((uint16_t)(1U << (canal - 1)));
  Serial.print(F("PRUEBA canal "));
  Serial.print(canal);
  Serial.println(F(" -> HIGH 250 ms; todos los demas LOW"));
}

void procesarCaracter(char c) {
  if (c == 'S' || c == 's') {
    detener();
    longitud = 0;
    lineaInvalida = false;
    Serial.println(F("STOP -> todas las salidas LOW"));
    return;
  }
  if (c == '\n' || c == '\r') {
    if (lineaInvalida) {
      Serial.println(F("Entrada rechazada. Usa 1..16 + Enter o S."));
    } else if (longitud > 0) {
      uint8_t canal = 0;
      for (uint8_t i = 0; i < longitud; ++i) canal = canal * 10 + (numero[i] - '0');
      probar(canal);
    }
    longitud = 0;
    lineaInvalida = false;
    return;
  }
  if (lineaInvalida) return;
  if (c >= '0' && c <= '9' && longitud < 2) {
    numero[longitud++] = c;
  } else {
    detener();
    longitud = 0;
    lineaInvalida = true;
  }
}

void setup() {
  pinMode(PIN_DS, OUTPUT);
  pinMode(PIN_STCP, OUTPUT);
  pinMode(PIN_SHCP, OUTPUT);
  digitalWrite(PIN_DS, LOW);
  digitalWrite(PIN_STCP, LOW);
  digitalWrite(PIN_SHCP, LOW);
  escribir16(0x0000);
  Serial.begin(115200);
  Serial.println();
  Serial.println(F("DIAGNOSTICO DE SALIDAS - ESP32"));
  Serial.println(F("DS=5 | STCP/latch=18 | SHCP/reloj=19"));
  Serial.println(F("Reposo: todas las salidas LOW."));
  Serial.println(F("1..16 + Enter = pulso individual de 250 ms."));
  Serial.println(F("S = todas LOW inmediatamente."));
  Serial.println(F("Prueba y anota UN canal a la vez. No hay barrido automatico."));
}

void loop() {
  actualizarPulso();
  // Acotar la lectura para atender el temporizador incluso con entrada continua.
  for (uint8_t i = 0; i < 32 && Serial.available() > 0; ++i) {
    procesarCaracter((char)Serial.read());
    actualizarPulso();
  }
}
