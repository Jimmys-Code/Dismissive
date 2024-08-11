class EchoCancellerProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.filterLength = 1024;
        this.filterCoefficients = new Float32Array(this.filterLength);
        this.delayBuffer = new Float32Array(this.filterLength);
        this.delayIndex = 0;
    }

    process(inputs, outputs) {
        const fileInput = inputs[0][0];
        const micInput = inputs[1][0];
        const output = outputs[0][0];

        for (let i = 0; i < 128; i++) {
            // Store the reference signal (file audio) in the delay buffer
            this.delayBuffer[this.delayIndex] = fileInput[i];
            this.delayIndex = (this.delayIndex + 1) % this.filterLength;

            // Compute the estimated echo
            let estimatedEcho = 0;
            for (let j = 0; j < this.filterLength; j++) {
                const delayIndex = (this.delayIndex + j) % this.filterLength;
                estimatedEcho += this.filterCoefficients[j] * this.delayBuffer[delayIndex];
            }

            // Subtract the estimated echo from the microphone input
            output[i] = micInput[i] - estimatedEcho;

            // Update filter coefficients using LMS algorithm
            const learningRate = 0.1;
            const error = output[i];
            for (let j = 0; j < this.filterLength; j++) {
                const delayIndex = (this.delayIndex + j) % this.filterLength;
                this.filterCoefficients[j] += learningRate * error * this.delayBuffer[delayIndex];
            }
        }

        return true;
    }
}

registerProcessor('echo-canceller', EchoCancellerProcessor);