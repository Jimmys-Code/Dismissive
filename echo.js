const NodeWebRTC = require('node-webrtc');

async function setupEchoCancellation() {
  // Create a MediaStream
  const audioStream = new NodeWebRTC.MediaStream();

  // Create an audio source (this simulates a microphone input)
  const audioSource = new NodeWebRTC.RTCAudioSource();

  // Create an audio track from the source
  const audioTrack = audioSource.createTrack();

  // Add the audio track to the stream
  audioStream.addTrack(audioTrack);

  // Create a peer connection
  const pc = new NodeWebRTC.RTCPeerConnection();

  // Add the audio track to the peer connection
  pc.addTrack(audioTrack, audioStream);

  // Create a transceiver for the audio
  const transceiver = pc.addTransceiver('audio', { direction: 'sendrecv' });

  // Enable echo cancellation
  await transceiver.sender.setParameters({
    encodings: [{ dtx: true }],
    echoCancellation: true
  });

  console.log('Echo cancellation enabled');

  // Simulate audio input (replace this with actual audio input in a real scenario)
  setInterval(() => {
    const sampleRate = 48000;
    const channelCount = 1;
    const samples = new Int16Array(sampleRate * channelCount / 10); // 100ms of audio
    for (let i = 0; i < samples.length; i++) {
      samples[i] = Math.floor(Math.sin(i / 10) * 10000); // Simple sine wave
    }

    audioSource.onData({
      samples: samples,
      sampleRate: sampleRate,
      channelCount: channelCount,
      bitsPerSample: 16
    });
  }, 100);

  // Handle the processed audio
  pc.ontrack = (event) => {
    const { track } = event;
    console.log('Received processed audio track');

    // In a real scenario, you would do something with this processed audio
    // For example, send it to another peer or save it to a file
    
    const sink = new NodeWebRTC.RTCAudioSink(track);
    sink.ondata = (data) => {
      console.log('Received processed audio data:', data.samples.length, 'samples');
      // Here you could write the processed audio to a file or send it somewhere
    };
  };

  // Create and set local description (offer)
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  console.log('Local description set');

  // In a real scenario, you would send this offer to a remote peer
  // and handle the answer. For this example, we'll set a local answer.
  const answer = await pc.createAnswer();
  await pc.setRemoteDescription(answer);

  console.log('Remote description set');
}

setupEchoCancellation().catch(console.error);
