let audioContext;
let serverAudioBuffer;
let processedStream;
let serverSource;
let processedSource;
let analyserServer;
let analyserProcessed;
let audioElement;
let mediaRecorder;
let recordedChunks = [];
let inputGainNode;
let outputGainNode;

const audioFileInput = document.getElementById('audioFileInput');
const playButton = document.getElementById('playButton');
const playServerButton = document.getElementById('playServerButton');
const startRecordingButton = document.getElementById('startRecordingButton');
const stopRecordingButton = document.getElementById('stopRecordingButton');
const micCanvas = document.getElementById('micCanvas');
const processedCanvas = document.getElementById('processedCanvas');
const micCtx = micCanvas.getContext('2d');
const processedCtx = processedCanvas.getContext('2d');
const inputVolumeControl = document.getElementById('inputVolumeControl');
const inputVolumeValue = document.getElementById('inputVolumeValue');
const outputVolumeControl = document.getElementById('outputVolumeControl');
const outputVolumeValue = document.getElementById('outputVolumeValue');

playButton.addEventListener('click', playLocalAudioFile);
playServerButton.addEventListener('click', requestServerAudioFile);
startRecordingButton.addEventListener('click', startRecording);
stopRecordingButton.addEventListener('click', stopRecording);
inputVolumeControl.addEventListener('input', updateInputVolume);
outputVolumeControl.addEventListener('input', updateOutputVolume);

// Start audio processing immediately
window.addEventListener('load', startAudioProcessing);

const socket = io();

socket.on('audio_data', function(data) {
    if (serverAudioBuffer) {
        serverAudioBuffer.copyToChannel(new Float32Array(data.data), 0);
    }
});

socket.on('audio_file_data', function(data) {
    playServerAudioFile(data.data);
});

socket.on('waveform_update', function(data) {
    const waveformPlot = document.getElementById('waveformPlot');
    waveformPlot.src = 'data:image/png;base64,' + data.plot;
});

async function startAudioProcessing() {
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();

        // Set up server audio input
        serverAudioBuffer = audioContext.createBuffer(1, 1024, 44100);
        serverSource = audioContext.createBufferSource();
        serverSource.buffer = serverAudioBuffer;
        serverSource.loop = true;
        serverSource.start();

        // Set up processed stream with echo cancellation
        const constraints = {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: false
        };
        processedStream = await navigator.mediaDevices.getUserMedia({ audio: constraints });
        processedSource = audioContext.createMediaStreamSource(processedStream);

        // Create and connect input gain node
        inputGainNode = audioContext.createGain();
        inputGainNode.gain.value = 1.0;
        processedSource.connect(inputGainNode);

        // Create and connect output gain node
        outputGainNode = audioContext.createGain();
        outputGainNode.gain.value = 1.0;

        // Set up analyzers
        analyserServer = audioContext.createAnalyser();
        analyserProcessed = audioContext.createAnalyser();
        analyserServer.fftSize = 2048;
        analyserProcessed.fftSize = 2048;

        serverSource.connect(analyserServer);
        inputGainNode.connect(outputGainNode);
        outputGainNode.connect(analyserProcessed);

        // Create a ScriptProcessorNode to capture processed audio
        const scriptNode = audioContext.createScriptProcessor(1024, 1, 1);
        outputGainNode.connect(scriptNode);
        scriptNode.connect(audioContext.destination);

        scriptNode.onaudioprocess = function(audioProcessingEvent) {
            const inputBuffer = audioProcessingEvent.inputBuffer;
            const inputData = inputBuffer.getChannelData(0);
            sendProcessedAudioToServer(inputData);
        };

        // Start updating waveforms
        updateWaveforms();
    } catch (error) {
        console.error('Error starting audio processing:', error);
    }
}

function sendProcessedAudioToServer(audioData) {
    // Convert Float32Array to regular array for JSON serialization
    const dataArray = Array.from(audioData);
    socket.emit('processed_audio', { data: dataArray });
}

function updateInputVolume() {
    const volume = parseFloat(inputVolumeControl.value);
    inputGainNode.gain.setValueAtTime(volume, audioContext.currentTime);
    inputVolumeValue.textContent = volume.toFixed(1);
}

function updateOutputVolume() {
    const volume = parseFloat(outputVolumeControl.value);
    outputGainNode.gain.setValueAtTime(volume, audioContext.currentTime);
    outputVolumeValue.textContent = volume.toFixed(1);
}

async function playLocalAudioFile() {
    if (audioFileInput.files.length > 0) {
        const file = audioFileInput.files[0];
        const arrayBuffer = await file.arrayBuffer();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        
        if (audioElement) {
            audioElement.stop();
        }
        
        audioElement = audioContext.createBufferSource();
        audioElement.buffer = audioBuffer;
        audioElement.connect(audioContext.destination);
        audioElement.start();
    } else {
        alert('Please select an audio file first.');
    }
}

function requestServerAudioFile() {
    socket.emit('request_audio_file');
}

async function playServerAudioFile(base64Data) {
    const binaryString = atob(base64Data);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);

    if (audioElement) {
        audioElement.stop();
    }

    audioElement = audioContext.createBufferSource();
    audioElement.buffer = audioBuffer;
    audioElement.connect(audioContext.destination);
    audioElement.start();
}

function updateWaveforms() {
    const serverData = new Uint8Array(analyserServer.frequencyBinCount);
    const processedData = new Uint8Array(analyserProcessed.frequencyBinCount);
    
    analyserServer.getByteTimeDomainData(serverData);
    analyserProcessed.getByteTimeDomainData(processedData);

    drawWaveform(micCtx, serverData);
    drawWaveform(processedCtx, processedData);

    requestAnimationFrame(updateWaveforms);
}

function drawWaveform(ctx, data) {
    ctx.fillStyle = 'rgb(18, 18, 18)';
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    ctx.lineWidth = 2;
    ctx.strokeStyle = ctx.canvas.id === 'micCanvas' ? 'rgb(255, 255, 255)' : 'rgb(0, 255, 0)';

    ctx.beginPath();

    const sliceWidth = ctx.canvas.width * 1.0 / data.length;
    let x = 0;

    for (let i = 0; i < data.length; i++) {
        const v = data[i] / 128.0;
        const y = v * ctx.canvas.height / 2;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }

        x += sliceWidth;
    }

    ctx.lineTo(ctx.canvas.width, ctx.canvas.height / 2);
    ctx.stroke();
}

function startRecording() {
    recordedChunks = [];
    const dest = audioContext.createMediaStreamDestination();
    outputGainNode.connect(dest);

    mediaRecorder = new MediaRecorder(dest.stream);
    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
            recordedChunks.push(e.data);
        }
    };
    mediaRecorder.start();

    startRecordingButton.disabled = true;
    stopRecordingButton.disabled = false;
}

function stopRecording() {
    mediaRecorder.stop();
    startRecordingButton.disabled = false;
    stopRecordingButton.disabled = true;

    mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: 'audio/wav' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        document.body.appendChild(a);
        a.style = 'display: none';
        a.href = url;
        a.download = 'echo_cancelled_audio.wav';
        a.click();
        window.URL.revokeObjectURL(url);
    };
}

const darkModeToggle = document.getElementById('darkModeToggle');

darkModeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    micCanvas.classList.toggle('dark-mode');
    processedCanvas.classList.toggle('dark-mode');
});
