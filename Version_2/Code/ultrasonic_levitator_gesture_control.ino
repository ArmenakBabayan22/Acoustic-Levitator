#include <avr/io.h>
#include <avr/interrupt.h>

const int BASE_FREQ = 197;
volatile int currentFreq = BASE_FREQ;

String inputString = "";
bool stringComplete = false;

unsigned long lastReportTime = 0;
const unsigned long reportInterval = 200;

void setup() {
  DDRC |= 0b00000011; 
  Serial.begin(9600);
  inputString.reserve(20);

  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1  = 0;
  
  OCR1A = currentFreq;
  TCCR1B |= (1 << WGM12);
  TCCR1B |= (1 << CS10);
  TIMSK1 |= (1 << OCIE1A);
  interrupts();
}

ISR(TIMER1_COMPA_vect) {
  static bool state = false;
  state = !state;

  if (state) {
    PORTC = (PORTC & 0xFC) | 0b01;
  } else {
    PORTC = (PORTC & 0xFC) | 0b10;
  }
}

void loop() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }

  if (stringComplete) {
    inputString.trim();
    
    if (inputString.startsWith("SET:")) {
      String valStr = inputString.substring(4);
      int newOcr = valStr.toInt();
      
      if (newOcr >= 150 && newOcr <= 250) {
        noInterrupts();
        currentFreq = newOcr;
        OCR1A = currentFreq;
        interrupts();
      }
    }
    
    inputString = "";
    stringComplete = false;
  }

  unsigned long currentTime = millis();
  if (currentTime - lastReportTime >= reportInterval) {
    lastReportTime = currentTime;
    
    Serial.print("FREQ:");
    Serial.println(currentFreq);
  }
}
