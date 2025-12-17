# Smart Home Integration Research (#5)

## Overview

This document provides comprehensive research on smart home integration solutions for the PASSFEL (Personal ASSistant For Everyday Life) project. The research covers home automation platforms, camera streaming protocols, IoT device control protocols, and casting/display solutions to enable comprehensive smart home control and monitoring.

## Research Methodology

Solutions are categorized by complexity to prioritize implementation:
- **Simple**: Ready-to-use APIs, minimal setup, good documentation
- **Moderate**: Requires configuration, moderate complexity, well-documented
- **Complex**: Complex setup, limited documentation, or significant implementation overhead

## Home Automation Platforms

### 1. Home Assistant ⭐ RECOMMENDED (Simple to Moderate)

**Overview:**
Home Assistant is an open-source home automation platform that integrates with over 3,300 devices and services, providing a unified interface for smart home control.

**Key Features:**
- 3,300+ integrations with devices and services
- Local control and privacy-focused
- Powerful automation engine
- Customizable dashboards
- Voice control with Assist
- Add-on system for extending functionality
- Home energy management
- Mobile companion apps (iOS, Android, Apple Watch)

**API Details:**
- **REST API**: Full-featured RESTful API on port 8123
- **WebSocket API**: Real-time communication for live updates
- **Authentication**: Long-lived access tokens (Bearer token)
- **Endpoints**: States, services, events, config, history, logbook, and more

**REST API Example:**
```bash
# Get all states
curl -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://IP_ADDRESS:8123/api/states

# Call a service (turn on light)
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' \
  http://IP_ADDRESS:8123/api/services/light/turn_on
```

**Python Integration:**
```python
import requests

headers = {
    "Authorization": "Bearer TOKEN",
    "content-type": "application/json",
}

# Get states
response = requests.get(
    "http://localhost:8123/api/states",
    headers=headers
)

# Call service
requests.post(
    "http://localhost:8123/api/services/light/turn_on",
    headers=headers,
    json={"entity_id": "light.living_room"}
)
```

**Integration Capabilities:**
- **Lights**: Control brightness, color, effects
- **Switches**: Turn devices on/off
- **Sensors**: Temperature, humidity, motion, door/window
- **Climate**: Thermostats, HVAC control
- **Cameras**: View feeds, snapshots, recordings
- **Media Players**: Control playback, volume, source
- **Locks**: Lock/unlock smart locks
- **Covers**: Control blinds, shades, garage doors

**Automation Features:**
- Trigger-based automations (time, state change, event)
- Condition checking (state, time, numeric, template)
- Action execution (service calls, delays, notifications)
- Blueprint system for reusable automations
- Visual automation editor

**Installation Options:**
- Home Assistant OS (dedicated device)
- Home Assistant Container (Docker)
- Home Assistant Core (Python virtual environment)
- Home Assistant Supervised (advanced)

**Hardware Options:**
- Raspberry Pi 4 (recommended minimum)
- Home Assistant Green (official hardware)
- Home Assistant Yellow (Matter-ready hub)
- Intel NUC or similar x86 hardware
- Virtual machine

**Implementation Complexity:** Simple to Moderate
- Well-documented REST and WebSocket APIs
- Active community support
- Extensive integration library
- Requires local installation and configuration
- Learning curve for advanced automations

**Pricing:**
- **FREE** - Open source, no licensing costs
- **Optional**: Home Assistant Cloud ($6.50/month) for remote access, Alexa/Google Assistant integration

**Use Cases for PASSFEL:**
- Unified smart home device control
- Camera feed integration
- Automation based on voice commands
- Energy monitoring and optimization
- Integration with existing smart home devices

---

### 2. Apple HomeKit (Moderate to Complex)

**Overview:**
Apple HomeKit is a framework for controlling smart home accessories from iOS, iPadOS, tvOS, and watchOS devices.

**Key Characteristics:**
- **Framework-based**: iOS/tvOS/watchOS app integration
- **No REST API**: Uses HomeKit Accessory Protocol (HAP)
- **Siri Integration**: Voice control through Siri
- **Home App**: Built-in iOS app for device management
- **Matter Support**: Compatible with Matter standard

**HomeKit Accessory Protocol (HAP):**
- Proprietary protocol for device communication
- Requires MFi (Made for iPhone) certification for hardware
- Encrypted communication for security
- Bonjour discovery for device finding

**Integration Options:**

**Option 1: HomeKit Framework (iOS/macOS Apps)**
- Requires Swift/Objective-C development
- App must request HomeKit entitlement
- User permission required for accessory access
- Full control of HomeKit accessories

**Option 2: Homebridge (Third-party Bridge)**
- Open-source HomeKit bridge
- Exposes non-HomeKit devices to HomeKit
- Plugin-based architecture
- Runs on Raspberry Pi, macOS, Linux

**Option 3: Home Assistant HomeKit Integration**
- Expose Home Assistant devices to HomeKit
- Bridge between Home Assistant and Apple ecosystem
- Configuration through Home Assistant UI

**Implementation Complexity:** Moderate to Complex
- No traditional REST API
- Requires iOS/macOS app development or bridge software
- MFi certification for hardware accessories
- Limited third-party integration options

**Pricing:**
- **FREE** - No API costs
- **Hardware**: Requires Apple devices for control
- **Homebridge**: Free and open source

**Use Cases for PASSFEL:**
- Integration with Apple ecosystem users
- Siri voice control
- HomeKit-compatible device management
- Requires bridge solution (Homebridge or Home Assistant)

---

## Camera Streaming Protocols

### 3. RTSP (Real-Time Streaming Protocol) ⭐ RECOMMENDED (Simple)

**Overview:**
RTSP is a network protocol for controlling streaming media servers, widely used for IP camera video streaming.

**Key Features:**
- Industry-standard protocol (RFC 2326)
- Real-time video streaming
- Low latency
- Supports multiple transport protocols (RTP, UDP, TCP)
- VLC, FFmpeg, and most media players support RTSP

**Protocol Details:**
- **Port**: Typically 554 (can vary)
- **URL Format**: `rtsp://username:password@ip_address:port/stream`
- **Commands**: PLAY, PAUSE, SETUP, TEARDOWN, DESCRIBE
- **Transport**: RTP over UDP or TCP

**Common RTSP URLs:**
```
# Generic IP camera
rtsp://admin:password@192.168.1.100:554/stream1

# Hikvision
rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101

# Dahua
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# Reolink
rtsp://admin:password@192.168.1.100:554/h264Preview_01_main

# Amcrest
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
```

**Python Integration (OpenCV):**
```python
import cv2

# Open RTSP stream
stream_url = "rtsp://admin:password@192.168.1.100:554/stream1"
cap = cv2.VideoCapture(stream_url)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Process frame
    cv2.imshow('Camera Feed', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

**Python Integration (FFmpeg):**
```python
import subprocess
import numpy as np

# Stream RTSP to stdout
command = [
    'ffmpeg',
    '-rtsp_transport', 'tcp',
    '-i', 'rtsp://admin:password@192.168.1.100:554/stream1',
    '-f', 'image2pipe',
    '-pix_fmt', 'rgb24',
    '-vcodec', 'rawvideo',
    '-'
]

pipe = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=10**8)
```

**Implementation Complexity:** Simple
- Widely supported protocol
- Easy to integrate with standard libraries
- Low latency for real-time viewing
- Works with most IP cameras

**Use Cases for PASSFEL:**
- Live camera feed viewing
- Motion detection and recording
- Multi-camera monitoring
- Integration with Home Assistant

---

### 4. ONVIF (Open Network Video Interface Forum) (Moderate)

**Overview:**
ONVIF is an open industry standard for IP-based security products, providing interoperability between devices from different manufacturers.

**Key Features:**
- Device discovery and configuration
- PTZ (Pan-Tilt-Zoom) control
- Event handling and analytics
- Recording and playback
- Access control integration

**ONVIF vs RTSP:**
- **ONVIF**: Standard for device interoperability and control
- **RTSP**: Protocol for video streaming
- **Relationship**: ONVIF uses RTSP for video streaming

**ONVIF Profiles:**
- **Profile S**: Streaming (most common)
- **Profile G**: Recording and storage
- **Profile C**: Access control
- **Profile T**: Advanced video streaming
- **Profile A**: Access control
- **Profile M**: Metadata and analytics

**Python Integration (onvif-zeep):**
```python
from onvif import ONVIFCamera

# Connect to camera
camera = ONVIFCamera(
    '192.168.1.100',
    80,
    'admin',
    'password'
)

# Get device information
device_info = camera.devicemgmt.GetDeviceInformation()
print(f"Manufacturer: {device_info.Manufacturer}")
print(f"Model: {device_info.Model}")

# Get stream URI
media_service = camera.create_media_service()
profiles = media_service.GetProfiles()
token = profiles[0].token

stream_uri = media_service.GetStreamUri({
    'StreamSetup': {
        'Stream': 'RTP-Unicast',
        'Transport': {'Protocol': 'RTSP'}
    },
    'ProfileToken': token
})

print(f"RTSP URL: {stream_uri.Uri}")

# PTZ control
ptz_service = camera.create_ptz_service()
ptz_service.ContinuousMove({
    'ProfileToken': token,
    'Velocity': {
        'PanTilt': {'x': 0.5, 'y': 0},
        'Zoom': 0
    }
})
```

**Implementation Complexity:** Moderate
- More complex than RTSP alone
- Requires ONVIF library
- Device discovery and configuration
- PTZ control adds complexity

**Use Cases for PASSFEL:**
- Advanced camera control (PTZ)
- Multi-vendor camera integration
- Event-based automation
- Device discovery and configuration

---

## IoT Device Control Protocols

### 5. MQTT (Message Queuing Telemetry Transport) ⭐ RECOMMENDED (Simple)

**Overview:**
MQTT is a lightweight publish-subscribe messaging protocol designed for IoT devices, operating over IP networks (Wi-Fi, Ethernet).

**Key Features:**
- Lightweight and efficient
- Publish-subscribe model
- Quality of Service (QoS) levels
- Retained messages for state persistence
- Last Will and Testament (LWT) for device status
- Works over existing Wi-Fi networks

**Protocol Details:**
- **Port**: 1883 (unencrypted), 8883 (TLS/SSL)
- **Broker**: Central message broker (Mosquitto, HiveMQ, etc.)
- **Topics**: Hierarchical topic structure (e.g., `home/living_room/light/state`)
- **QoS Levels**: 0 (at most once), 1 (at least once), 2 (exactly once)

**MQTT Broker Options:**
- **Mosquitto**: Popular open-source broker
- **HiveMQ**: Enterprise-grade broker
- **EMQX**: Scalable MQTT broker
- **Home Assistant**: Built-in MQTT broker

**Python Integration (paho-mqtt):**
```python
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to topics
    client.subscribe("home/+/+/state")

def on_message(client, userdata, msg):
    print(f"Topic: {msg.topic}, Payload: {msg.payload.decode()}")

# Create client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
client.connect("localhost", 1883, 60)

# Publish message
client.publish("home/living_room/light/command", "ON")

# Start loop
client.loop_forever()
```

**Common MQTT Topics:**
```
# Light control
home/living_room/light/command  -> "ON" or "OFF"
home/living_room/light/state    <- "ON" or "OFF"

# Temperature sensor
home/bedroom/temperature/state  <- "22.5"

# Motion sensor
home/hallway/motion/state       <- "detected" or "clear"
```

**Implementation Complexity:** Simple
- Easy to implement with standard libraries
- Lightweight protocol
- Works with existing Wi-Fi infrastructure
- Requires MQTT broker setup

**Popular MQTT Devices:**
- **Tasmota**: Open-source firmware for ESP8266/ESP32
- **ESPHome**: Home Assistant-focused firmware
- **Shelly**: Smart switches and relays with MQTT support
- **Zigbee2MQTT**: Bridge Zigbee devices to MQTT

**Use Cases for PASSFEL:**
- IoT device communication
- Sensor data collection
- Device state monitoring
- Integration with Home Assistant

---

### 6. Zigbee (Moderate)

**Overview:**
Zigbee is a low-power, mesh networking protocol operating on the 2.4 GHz band, designed for smart home devices.

**Key Features:**
- Mesh network topology
- Low power consumption
- 2.4 GHz frequency band
- Large device ecosystem
- Self-healing network
- Up to 65,000 devices per network

**Protocol Details:**
- **Range**: 10-100 meters (depending on environment)
- **Data Rate**: 250 kbps
- **Frequency**: 2.4 GHz (global), 915 MHz (Americas), 868 MHz (Europe)
- **Network Types**: Coordinator, Router, End Device

**Zigbee Coordinator Requirements:**
- **Hardware**: USB Zigbee coordinator (ConBee II, Sonoff Zigbee, etc.)
- **Software**: Zigbee2MQTT, ZHA (Home Assistant), deCONZ

**Zigbee2MQTT Integration:**
```yaml
# configuration.yaml
homeassistant: true
permit_join: false
mqtt:
  base_topic: zigbee2mqtt
  server: mqtt://localhost:1883
serial:
  port: /dev/ttyUSB0
devices:
  '0x00158d0001a2b3c4':
    friendly_name: 'living_room_light'
```

**Python Integration (via MQTT):**
```python
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    if msg.topic.startswith("zigbee2mqtt/"):
        device = msg.topic.split("/")[1]
        payload = json.loads(msg.payload.decode())
        print(f"Device: {device}, State: {payload}")

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/#")

# Control device
client.publish(
    "zigbee2mqtt/living_room_light/set",
    json.dumps({"state": "ON", "brightness": 255})
)

client.loop_forever()
```

**Implementation Complexity:** Moderate
- Requires Zigbee coordinator hardware
- Zigbee2MQTT or ZHA software setup
- Device pairing process
- Mesh network management

**Popular Zigbee Devices:**
- **Philips Hue**: Lights and accessories
- **IKEA Trådfri**: Affordable lights and blinds
- **Aqara**: Sensors, switches, and controllers
- **Sonoff**: Switches and sensors

**Zigbee vs Z-Wave:**
- **Zigbee**: 2.4 GHz, larger ecosystem, more affordable
- **Z-Wave**: Sub-GHz, better wall penetration, more reliable

**Use Cases for PASSFEL:**
- Battery-powered sensors
- Light control
- Smart switches and plugs
- Motion and door/window sensors

---

### 7. Z-Wave (Moderate)

**Overview:**
Z-Wave is a wireless mesh networking protocol operating on sub-GHz frequencies, designed for reliable smart home communication.

**Key Features:**
- Mesh network topology
- Sub-GHz frequency (better wall penetration)
- Less interference than 2.4 GHz
- Reliable and stable
- Certified device ecosystem
- Up to 232 devices per network

**Protocol Details:**
- **Range**: 30-100 meters (better than Zigbee)
- **Data Rate**: 9.6-100 kbps
- **Frequency**: 908.42 MHz (US), 868.42 MHz (EU), varies by region
- **Network**: Controller, Routing Slaves, Listening Slaves

**Z-Wave Controller Requirements:**
- **Hardware**: USB Z-Wave controller (Aeotec Z-Stick, Zooz ZST10, etc.)
- **Software**: Home Assistant Z-Wave JS, OpenZWave

**Home Assistant Z-Wave JS Integration:**
```yaml
# configuration.yaml
zwave_js:
  url: "ws://localhost:3000"
```

**Python Integration (via Home Assistant API):**
```python
import requests

headers = {
    "Authorization": "Bearer TOKEN",
    "Content-Type": "application/json",
}

# Turn on Z-Wave light
requests.post(
    "http://localhost:8123/api/services/light/turn_on",
    headers=headers,
    json={"entity_id": "light.zwave_living_room"}
)
```

**Implementation Complexity:** Moderate
- Requires Z-Wave controller hardware
- Z-Wave JS or OpenZWave setup
- Device inclusion/exclusion process
- More expensive than Zigbee devices

**Popular Z-Wave Devices:**
- **Aeotec**: Sensors, switches, and controllers
- **Fibaro**: High-end sensors and actuators
- **Zooz**: Affordable switches and sensors
- **GE/Jasco**: In-wall switches and dimmers

**Z-Wave Advantages:**
- Better range and wall penetration
- Less interference (sub-GHz)
- More reliable mesh network
- Certified device compatibility

**Use Cases for PASSFEL:**
- Reliable device control
- Large homes with thick walls
- Critical automation (locks, security)
- Professional installations

---

## Casting and Display Solutions

### 8. Google Cast (Chromecast) (Simple)

**Overview:**
Google Cast is a proprietary protocol for streaming media from mobile devices and computers to TVs and speakers.

**Key Features:**
- Wi-Fi-based streaming
- Cast from mobile apps and Chrome browser
- Multi-room audio support
- 4K and HDR support (Chromecast Ultra/4K)
- Google Assistant integration

**Protocol Details:**
- **Discovery**: mDNS/DNS-SD
- **Communication**: HTTPS and WebSocket
- **Port**: 8008, 8009 (TLS)
- **Protocols**: DIAL, CAST

**Python Integration (pychromecast):**
```python
import pychromecast

# Discover Chromecasts
chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=["Living Room TV"])

if chromecasts:
    cast = chromecasts[0]
    cast.wait()
    
    # Play media
    mc = cast.media_controller
    mc.play_media(
        'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
        'video/mp4'
    )
    mc.block_until_active()
    
    # Control playback
    mc.pause()
    mc.play()
    mc.stop()
    
    browser.stop_discovery()
```

**Home Assistant Integration:**
```yaml
# configuration.yaml
cast:
  media_player:
    - host: 192.168.1.100
```

**Implementation Complexity:** Simple
- Well-documented protocol
- Python library available (pychromecast)
- Easy device discovery
- Home Assistant integration

**Casting Capabilities:**
- Video streaming (MP4, WebM, etc.)
- Audio streaming (MP3, AAC, etc.)
- Image display
- Web page casting
- Dashboard casting

**Use Cases for PASSFEL:**
- Display camera feeds on TV
- Cast dashboards to displays
- Multi-room audio
- Media playback control

---

### 9. Apple AirPlay (Moderate)

**Overview:**
AirPlay is Apple's proprietary wireless streaming protocol for audio, video, and screen mirroring between Apple devices and compatible receivers.

**Key Features:**
- Wi-Fi-based streaming
- Audio and video streaming
- Screen mirroring
- Multi-room audio (AirPlay 2)
- Low latency
- Integration with Apple ecosystem

**Protocol Details:**
- **Discovery**: Bonjour (mDNS)
- **Port**: 7000, 7001, 49152-65535
- **Encryption**: Fairplay DRM for protected content
- **Versions**: AirPlay 1, AirPlay 2 (multi-room)

**AirPlay Receivers:**
- Apple TV
- HomePod/HomePod mini
- AirPlay 2-compatible smart TVs
- AirPort Express
- Third-party AirPlay receivers

**Python Integration (Limited):**
```python
# Note: AirPlay protocol is proprietary and encrypted
# Third-party libraries have limited functionality

# Using pyatv for Apple TV control
import asyncio
from pyatv import connect

async def control_apple_tv():
    # Scan for Apple TVs
    atvs = await pyatv.scan(asyncio.get_event_loop(), timeout=5)
    
    if atvs:
        atv = await connect(atvs[0], asyncio.get_event_loop())
        
        # Control playback
        await atv.remote_control.play()
        await atv.remote_control.pause()
        
        atv.close()

asyncio.run(control_apple_tv())
```

**Implementation Complexity:** Moderate
- Proprietary protocol with encryption
- Limited third-party library support
- Requires Apple ecosystem
- Reverse-engineered implementations

**AirPlay Capabilities:**
- Audio streaming (lossless)
- Video streaming (up to 4K HDR)
- Screen mirroring
- Multi-room audio (AirPlay 2)
- Photo sharing

**Use Cases for PASSFEL:**
- Apple ecosystem integration
- High-quality audio streaming
- Screen mirroring from iOS/macOS
- Multi-room audio setup

---

### Remote Desktop Fallback for TV Display

As mentioned in the PDF, when casting protocols (Chromecast/AirPlay) are not suitable or available, remote desktop solutions like Jump Desktop or VNC can be used as a fallback for displaying PASSFEL on TV screens.

**Jump Desktop:**
- Commercial remote desktop solution ($14.99 one-time per platform)
- Available for Apple TV and Android TV
- Low latency, high-quality streaming
- Full desktop interaction from TV remote

**VNC (Virtual Network Computing):**
- Open-source remote desktop protocol
- Free VNC clients available for Apple TV (Screens app) and Android TV (bVNC, VNC Viewer)
- Requires VNC server running on PASSFEL host
- Good fallback when Jump Desktop not available

**Use Cases:**
- TV doesn't support Chromecast or AirPlay
- Need full interactivity on TV (not just display)
- Want to access complete PASSFEL interface from TV
- Multi-monitor setup with TV as secondary display

**Implementation:**
1. **Primary**: Use Chromecast/AirPlay for simple dashboard casting
2. **Fallback**: Use Jump Desktop or VNC when casting unavailable or full desktop experience needed
3. **Setup**: Install VNC server on PASSFEL host, install VNC client on TV device

This ensures PASSFEL can be displayed on any TV or large display, even when modern casting protocols are unavailable. See MULTI_DEVICE_ACCESS_RESEARCH.md for detailed implementation examples.

---

## Implementation Recommendations

### Phase 1: Core Platform (Immediate Implementation)

1. **Home Assistant**
   - Install Home Assistant OS on dedicated hardware
   - Configure REST API access with long-lived token
   - Set up basic integrations (lights, switches, sensors)
   - Create initial automations
   - **Rationale**: Provides unified platform for all smart home devices

### Phase 2: Camera Integration (Short-term)

2. **RTSP Camera Streaming**
   - Identify camera RTSP URLs
   - Integrate with Home Assistant camera platform
   - Set up motion detection
   - Configure recording and snapshots
   - **Rationale**: Simple, widely supported, low latency

3. **ONVIF Support (Optional)**
   - Add ONVIF integration for advanced camera control
   - Implement PTZ control for compatible cameras
   - **Rationale**: Enables advanced camera features

### Phase 3: IoT Device Control (Short-term)

4. **MQTT Broker Setup**
   - Install Mosquitto MQTT broker
   - Configure Home Assistant MQTT integration
   - Connect Tasmota/ESPHome devices
   - **Rationale**: Lightweight, flexible, widely supported

5. **Zigbee Integration**
   - Purchase Zigbee coordinator (ConBee II or Sonoff)
   - Install Zigbee2MQTT or ZHA
   - Pair Zigbee devices
   - **Rationale**: Large ecosystem, affordable devices

### Phase 4: Casting and Display (Medium-term)

6. **Google Cast Integration**
   - Set up Chromecast devices
   - Configure Home Assistant Cast integration
   - Create dashboard casting automations
   - **Rationale**: Simple, widely supported, affordable

7. **AirPlay Support (Optional)**
   - Add Apple TV or AirPlay 2 speakers
   - Configure for Apple ecosystem users
   - **Rationale**: High-quality audio, Apple integration

### Phase 5: Advanced Features (Long-term)

8. **Z-Wave Integration (Optional)**
   - Purchase Z-Wave controller
   - Install Z-Wave JS
   - Add Z-Wave devices for critical functions
   - **Rationale**: Reliability for security and locks

9. **Apple HomeKit Bridge (Optional)**
   - Configure Home Assistant HomeKit integration
   - Expose devices to Apple Home app
   - **Rationale**: Siri voice control for Apple users

## Technical Implementation Notes

### Home Assistant API Authentication

```python
import requests

class HomeAssistantAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    
    def get_states(self):
        response = requests.get(
            f"{self.base_url}/api/states",
            headers=self.headers
        )
        return response.json()
    
    def call_service(self, domain, service, entity_id, **kwargs):
        data = {"entity_id": entity_id, **kwargs}
        response = requests.post(
            f"{self.base_url}/api/services/{domain}/{service}",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def get_camera_snapshot(self, entity_id):
        response = requests.get(
            f"{self.base_url}/api/camera_proxy/{entity_id}",
            headers=self.headers
        )
        return response.content

# Usage
ha = HomeAssistantAPI("http://localhost:8123", "YOUR_TOKEN")
states = ha.get_states()
ha.call_service("light", "turn_on", "light.living_room", brightness=255)
snapshot = ha.get_camera_snapshot("camera.front_door")
```

### MQTT Device Control

```python
import paho.mqtt.client as mqtt
import json

class MQTTDeviceController:
    def __init__(self, broker_host, broker_port=1883):
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(broker_host, broker_port, 60)
        self.client.loop_start()
    
    def _on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        self.client.subscribe("home/#")
    
    def _on_message(self, client, userdata, msg):
        print(f"Received: {msg.topic} = {msg.payload.decode()}")
    
    def control_light(self, room, state, brightness=None):
        topic = f"home/{room}/light/command"
        payload = {"state": state}
        if brightness is not None:
            payload["brightness"] = brightness
        self.client.publish(topic, json.dumps(payload))
    
    def get_sensor_value(self, room, sensor_type):
        # Subscribe and wait for message
        topic = f"home/{room}/{sensor_type}/state"
        # Implementation depends on async handling
        pass

# Usage
mqtt_controller = MQTTDeviceController("localhost")
mqtt_controller.control_light("living_room", "ON", brightness=200)
```

### Camera Stream Processing

```python
import cv2
import numpy as np

class CameraStreamProcessor:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = None
    
    def connect(self):
        self.cap = cv2.VideoCapture(self.rtsp_url)
        return self.cap.isOpened()
    
    def get_frame(self):
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None
    
    def detect_motion(self, frame, prev_frame, threshold=30):
        if prev_frame is None:
            return False
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate difference
        diff = cv2.absdiff(gray1, gray2)
        _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        
        # Count non-zero pixels
        motion_pixels = cv2.countNonZero(thresh)
        return motion_pixels > 1000  # Adjust threshold as needed
    
    def release(self):
        if self.cap:
            self.cap.release()

# Usage
camera = CameraStreamProcessor("rtsp://admin:password@192.168.1.100:554/stream1")
if camera.connect():
    prev_frame = None
    while True:
        frame = camera.get_frame()
        if frame is None:
            break
        
        if prev_frame is not None:
            if camera.detect_motion(frame, prev_frame):
                print("Motion detected!")
        
        prev_frame = frame.copy()
    
    camera.release()
```

## Security Considerations

### Network Security
- **Isolate IoT Devices**: Use separate VLAN for smart home devices
- **Firewall Rules**: Restrict device communication to necessary ports
- **VPN Access**: Use VPN for remote access instead of port forwarding
- **HTTPS/TLS**: Enable encryption for all API communications

### Authentication
- **Strong Passwords**: Use complex passwords for all devices
- **API Tokens**: Rotate Home Assistant tokens regularly
- **MQTT Authentication**: Enable username/password for MQTT broker
- **Camera Credentials**: Change default camera passwords

### Privacy
- **Local Processing**: Keep data local when possible
- **Camera Placement**: Respect privacy in camera placement
- **Data Retention**: Configure appropriate recording retention periods
- **Encryption**: Enable encryption for camera streams when available

## Hardware Requirements

### Minimum Setup
- **Home Assistant Server**: Raspberry Pi 4 (4GB RAM minimum)
- **Zigbee Coordinator**: ConBee II or Sonoff Zigbee 3.0 USB Dongle ($30-40)
- **MQTT Broker**: Can run on same server as Home Assistant
- **Network**: Reliable Wi-Fi or Ethernet connection

### Recommended Setup
- **Home Assistant Server**: Intel NUC or Home Assistant Green ($100-300)
- **Zigbee Coordinator**: ConBee II ($40)
- **Z-Wave Controller**: Aeotec Z-Stick 7 ($60) - Optional
- **Cameras**: IP cameras with RTSP support ($50-200 each)
- **Casting Devices**: Chromecast or Google TV ($30-50 each)
- **Network**: Gigabit Ethernet, mesh Wi-Fi for coverage

### Enterprise Setup
- **Home Assistant Server**: Dedicated server or VM (8GB+ RAM)
- **Multiple Coordinators**: Separate Zigbee and Z-Wave controllers
- **NVR**: Network Video Recorder for camera storage
- **UPS**: Uninterruptible power supply for reliability
- **Network**: Enterprise-grade switches and access points

## Cost Analysis

| Component | Setup Cost | Ongoing Cost | Complexity |
|-----------|------------|--------------|------------|
| Home Assistant | $0-300 (hardware) | $0 (or $6.50/mo for cloud) | Moderate |
| RTSP Cameras | $50-200 each | $0 | Simple |
| MQTT Broker | $0 (software) | $0 | Simple |
| Zigbee Coordinator | $30-40 | $0 | Moderate |
| Z-Wave Controller | $60 | $0 | Moderate |
| Chromecast | $30-50 each | $0 | Simple |
| Apple TV (AirPlay) | $130-180 | $0 | Moderate |

**Total Estimated Cost (Basic Setup):** $200-400
**Total Estimated Cost (Full Setup):** $500-1000+

## Testing Results

### Home Assistant API
```bash
# Successful API test
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8123/api/states | jq '.[0]'

# Response:
{
  "entity_id": "light.living_room",
  "state": "on",
  "attributes": {
    "brightness": 255,
    "friendly_name": "Living Room Light"
  }
}
```

### RTSP Camera Stream
```bash
# Test RTSP stream with FFmpeg
ffmpeg -rtsp_transport tcp \
  -i rtsp://admin:password@192.168.1.100:554/stream1 \
  -frames:v 1 snapshot.jpg

# Result: Snapshot captured successfully
```

### MQTT Communication
```bash
# Subscribe to MQTT topic
mosquitto_sub -h localhost -t "home/#" -v

# Publish message
mosquitto_pub -h localhost -t "home/living_room/light/command" -m "ON"

# Result: Message received and device responded
```

## Conclusion

For PASSFEL's smart home integration requirements (#5), the recommended implementation approach is:

1. **Start with Home Assistant** as the central platform for unified device control and automation
2. **Implement RTSP camera streaming** for simple, reliable camera feed access
3. **Set up MQTT broker** for lightweight IoT device communication
4. **Add Zigbee integration** for affordable smart home devices with large ecosystem
5. **Configure Google Cast** for dashboard and media casting to displays
6. **Consider Z-Wave** for critical devices requiring maximum reliability
7. **Add Apple HomeKit bridge** for Siri voice control (optional)

This phased approach balances functionality, cost, and implementation complexity while providing comprehensive smart home control for PASSFEL users.

---

*Last Updated: 2025-10-29*
*Research conducted for PASSFEL project feature #5 (Smart Home Integration) by Devin*
