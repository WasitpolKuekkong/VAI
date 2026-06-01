// Voice input composable — Web Speech API (STT) + Web Audio API (level meter)
// PTT: hold button to talk, release to send
// VAD: auto-listen, sends on each pause

export const useVoiceInput = (onTranscript: (text: string) => void) => {
  const isListening = ref(false)
  const isVAD = ref(false)
  const isPTT = ref(false)
  const transcript = ref('')
  const audioLevel = ref(0)
  const isSupported = ref(false)
  const hasPermission = ref(false)

  let recognition: any = null
  let audioCtx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let stream: MediaStream | null = null
  let levelRaf: number | null = null
  let vadRestartTimer: ReturnType<typeof setTimeout> | null = null

  onMounted(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    isSupported.value = !!(SR && navigator.mediaDevices?.getUserMedia)
  })

  // --- Audio level meter ---

  const startLevelMeter = async (): Promise<boolean> => {
    if (audioCtx) return true
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      hasPermission.value = true
      audioCtx = new AudioContext()
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 64
      const src = audioCtx.createMediaStreamSource(stream)
      src.connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        analyser!.getByteFrequencyData(data)
        const avg = data.reduce((s, v) => s + v, 0) / data.length
        audioLevel.value = Math.min(100, Math.round((avg / 128) * 200))
        levelRaf = requestAnimationFrame(tick)
      }
      tick()
      return true
    } catch {
      hasPermission.value = false
      return false
    }
  }

  const stopLevelMeter = () => {
    if (levelRaf) cancelAnimationFrame(levelRaf)
    levelRaf = null
    audioLevel.value = 0
    stream?.getTracks().forEach(t => t.stop())
    stream = null
    audioCtx?.close()
    audioCtx = null
    analyser = null
  }

  // --- Speech Recognition ---

  const createRecognition = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'th-TH'
    rec.interimResults = true
    rec.continuous = false
    rec.maxAlternatives = 1

    rec.onresult = (e: any) => {
      const result = e.results[e.results.length - 1]
      const text = result[0].transcript.trim()
      transcript.value = text
      if (result.isFinal && text) {
        onTranscript(text)
        transcript.value = ''
      }
    }

    rec.onerror = (e: any) => {
      if (e.error !== 'aborted' && e.error !== 'no-speech') {
        console.warn('[VAI Voice] STT error:', e.error)
      }
    }

    rec.onend = () => {
      isListening.value = false
      // VAD: auto-restart after each utterance ends
      if (isVAD.value) scheduleVADRestart()
    }

    return rec
  }

  const scheduleVADRestart = () => {
    if (!isVAD.value) return
    if (vadRestartTimer) clearTimeout(vadRestartTimer)
    vadRestartTimer = setTimeout(() => {
      if (isVAD.value) startSTT()
    }, 300)
  }

  const startSTT = () => {
    if (recognition) { try { recognition.abort() } catch {} }
    recognition = createRecognition()
    try {
      recognition.start()
      isListening.value = true
    } catch {}
  }

  const stopSTT = (abort = false) => {
    if (vadRestartTimer) clearTimeout(vadRestartTimer)
    transcript.value = ''
    isListening.value = false
    try {
      if (abort) recognition?.abort()
      else recognition?.stop()
    } catch {}
  }

  // --- Public API ---

  const toggleVAD = async () => {
    if (isVAD.value) {
      isVAD.value = false
      stopSTT(true)
      stopLevelMeter()
    } else {
      const ok = await startLevelMeter()
      if (ok) {
        isVAD.value = true
        startSTT()
      }
    }
  }

  // Hold startPTT, release stopPTT
  const startPTT = async () => {
    if (isPTT.value) return
    if (!hasPermission.value) {
      const ok = await startLevelMeter()
      if (!ok) return
    }
    isPTT.value = true
    transcript.value = ''
    startSTT()
  }

  const stopPTT = () => {
    if (!isPTT.value) return
    isPTT.value = false
    // stop() lets the browser finalize the current utterance before firing onend
    try { recognition?.stop() } catch {}
    if (!isVAD.value) stopLevelMeter()
  }

  onUnmounted(() => {
    isVAD.value = false
    stopSTT(true)
    stopLevelMeter()
  })

  return {
    isListening,
    isVAD,
    isPTT,
    transcript,
    audioLevel,
    isSupported,
    hasPermission,
    startPTT,
    stopPTT,
    toggleVAD,
  }
}
