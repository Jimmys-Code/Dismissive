import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

const EchoCancellationClient = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [audioData, setAudioData] = useState([]);
  const socketRef = useRef(null);
  const audioContextRef = useRef(null);
  const gainNodeRef = useRef(null);
  const echoCancellerRef = useRef(null);

  useEffect(() => {
    socketRef.current = io();

    socketRef.current.on('connect', () => {
      setIsConnected(true);
      console.log('Connected to server');
    });

    socketRef.current.on('disconnect', () => {
      setIsConnected(false);
      console.log('Disconnected from server');
    });

    socketRef.current.on('audio_data', handleAudioData);

    return () => {
      socketRef.current.disconnect();
    };
  }, []);

  const initAudio = async () => {
    console.log('Initializing audio');
    audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    gainNodeRef.current = audioContextRef.current.createGain();
    gainNodeRef.current.connect(audioContextRef.current.destination);

    echoCancellerRef.current = {
      filterLength: 1024,
      learningRate: 0.1,
      filterCoeffs: new Float32Array(1024).fill(0),
      buffer: new Float32Array(1024).fill(0),

      process(inputSignal, referenceSignal) {
        const outputSignal = new Float32Array(inputSignal.length);
        for (let i = 0; i < inputSignal.length; i++) {
          this.buffer.copyWithin(0, 1);
          this.buffer[this.filterLength - 1] = referenceSignal[i];
          const echoEstimate = this.filterCoeffs.reduce((sum, coeff, j) => sum + coeff * this.buffer[j], 0);
          const cleanedSample = inputSignal[i] - echoEstimate;
          this.filterCoeffs = this.filterCoeffs.map((coeff, j) => coeff + this.learningRate * cleanedSample * this.buffer[j]);
          outputSignal[i] = cleanedSample;
        }
        return outputSignal;
      }
    };
  };

  const handleAudioData = (data) => {
    if (!audioContextRef.current) {
      initAudio();
    }

    const micData = new Float32Array(data.mic_data);
    const playbackData = new Float32Array(data.playback_data);

    console.log('Received audio data:', { micDataLength: micData.length, playbackDataLength: playbackData.length });

    const processedData = echoCancellerRef.current.process(micData, playbackData);
    
    const audioBuffer = audioContextRef.current.createBuffer(1, processedData.length, audioContextRef.current.sampleRate);
    audioBuffer.copyToChannel(processedData, 0);

    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(gainNodeRef.current);
    source.start();

    socketRef.current.emit('processed_audio', { data: Array.from(processedData) });

    // Update state for waveform visualization
    setAudioData(prevData => {
      const newData = [...prevData, { 
        index: prevData.length, 
        mic: micData[0], 
        playback: playbackData[0], 
        processed: processedData[0] 
      }];
      return newData.slice(-100);  // Keep only the last 100 data points
    });
  };

  const handlePlayAudio = () => {
    console.log('Play audio button clicked');
    socketRef.current.emit('play_audio');
  };

  return (
    <div>
      <h1>Echo Cancellation Client</h1>
      <p>Connection status: {isConnected ? 'Connected' : 'Disconnected'}</p>
      <button onClick={handlePlayAudio}>Play Audio</button>
      <LineChart width={600} height={300} data={audioData}>
        <XAxis dataKey="index" />
        <YAxis />
        <CartesianGrid strokeDasharray="3 3" />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="mic" stroke="#8884d8" dot={false} />
        <Line type="monotone" dataKey="playback" stroke="#82ca9d" dot={false} />
        <Line type="monotone" dataKey="processed" stroke="#ffc658" dot={false} />
      </LineChart>
    </div>
  );
};

export default EchoCancellationClient;