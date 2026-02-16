import React, { useRef, useEffect, useState, Suspense } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { useAnimations } from '@react-three/drei';
import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader';

// Loading fallback
function LoadingSpinner() {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontSize: '12px'
    }}>
      Loading avatar...
    </div>
  );
}

// Error fallback
function ErrorFallback() {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#ff6b6b',
      fontSize: '12px',
      padding: '10px',
      textAlign: 'center'
    }}>
      Avatar unavailable
    </div>
  );
}

// Avatar Model Component
function AvatarModel({ avatarUrl, isTalking }) {
  const group = useRef();
  const [error, setError] = useState(false);
  
  let fbx = null;
  
  try {
    fbx = useLoader(FBXLoader, avatarUrl, (loader) => {
      // FBXLoader configuration
      loader.setPath('/models/');
    }, (error) => {
      console.error('FBX loading error:', error);
      setError(true);
    });
  } catch (err) {
    console.error('Avatar load failed:', err);
    setError(true);
    return null;
  }
  
  if (error || !fbx) {
    return null;
  }
  
  const { actions } = useAnimations(fbx.animations || [], group);
  
  // Play animation when talking
  useEffect(() => {
    if (actions && Object.keys(actions).length > 0) {
      const firstAnimation = Object.values(actions)[0];
      if (isTalking) {
        firstAnimation?.play();
      } else {
        firstAnimation?.stop();
      }
    }
  }, [isTalking, actions]);
  
  // Idle animation
  useFrame((state) => {
    if (group.current && !isTalking) {
      const time = state.clock.getElapsedTime();
      group.current.position.y = Math.sin(time * 0.8) * 0.02;
      group.current.rotation.y = Math.sin(time * 0.3) * 0.03;
    }
  });
  
  return (
    <primitive 
      ref={group} 
      object={fbx} 
      scale={0.01}
      position={[0, -1.2, 0]}
      rotation={[0, 0, 0]}
    />
  );
}

// Main Avatar Narrator Component
export default function AvatarNarrator({ 
  avatarUrl = "/models/business-avatar.fbx",
  position = "bottom-right",
  size = "medium",
  audioElement = null
}) {
  const [isTalking, setIsTalking] = useState(false);
  const [visible, setVisible] = useState(true);
  const [hasError, setHasError] = useState(false);
  
  // Audio detection
  useEffect(() => {
    if (!audioElement) return;
    
    let animationId;
    let audioContext;
    let analyser;
    let source;
    
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      
      if (!audioElement.connectedSource) {
        source = audioContext.createMediaElementSource(audioElement);
        audioElement.connectedSource = source;
        source.connect(analyser);
        analyser.connect(audioContext.destination);
      } else {
        source = audioElement.connectedSource;
      }
      
      analyser.fftSize = 256;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      
      const checkAudio = () => {
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setIsTalking(average > 5);
        animationId = requestAnimationFrame(checkAudio);
      };
      
      checkAudio();
    } catch (error) {
      console.error("Audio context error:", error);
    }
    
    return () => {
      if (animationId) cancelAnimationFrame(animationId);
    };
  }, [audioElement]);
  
  const positions = {
    "bottom-right": { bottom: "20px", right: "20px" },
    "bottom-left": { bottom: "20px", left: "20px" },
    "top-right": { top: "20px", right: "20px" },
    "top-left": { top: "20px", left: "20px" }
  };
  
  const sizes = {
    small: { width: "150px", height: "200px" },
    medium: { width: "200px", height: "280px" },
    large: { width: "280px", height: "380px" }
  };
  
  if (!visible) return null;
  
  return (
    <div 
      style={{
        position: "fixed",
        ...positions[position],
        ...sizes[size],
        zIndex: 1000,
        background: "linear-gradient(135deg, rgba(100, 50, 150, 0.85), rgba(50, 20, 100, 0.85))",
        borderRadius: "20px",
        border: "2px solid rgba(150, 100, 255, 0.6)",
        backdropFilter: "blur(10px)",
        boxShadow: "0 10px 40px rgba(0, 0, 0, 0.4)",
        overflow: "hidden"
      }}
    >
      <button
        onClick={() => setVisible(false)}
        style={{
          position: "absolute",
          top: "8px",
          right: "8px",
          background: "rgba(255, 255, 255, 0.2)",
          border: "none",
          borderRadius: "50%",
          width: "28px",
          height: "28px",
          cursor: "pointer",
          color: "white",
          fontSize: "18px",
          fontWeight: "bold",
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.2s"
        }}
        onMouseEnter={(e) => e.target.style.background = "rgba(255, 255, 255, 0.3)"}
        onMouseLeave={(e) => e.target.style.background = "rgba(255, 255, 255, 0.2)"}
      >
        ×
      </button>
      
      {isTalking && (
        <div
          style={{
            position: "absolute",
            top: "8px",
            left: "8px",
            background: "rgba(0, 255, 100, 0.2)",
            border: "2px solid rgba(0, 255, 100, 0.7)",
            borderRadius: "20px",
            padding: "4px 10px",
            fontSize: "11px",
            color: "white",
            fontWeight: "600",
            animation: "pulse 1.5s ease-in-out infinite",
            display: "flex",
            alignItems: "center",
            gap: "5px"
          }}
        >
          <span style={{ fontSize: "14px" }}>🎙️</span>
          Speaking
        </div>
      )}
      
      <Canvas
        camera={{ position: [0, 1.5, 3], fov: 45 }}
        style={{ width: "100%", height: "100%" }}
        onCreated={({ gl }) => {
          gl.setClearColor('#00000000', 0);
        }}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[5, 5, 5]} intensity={1.2} />
        <pointLight position={[-5, 5, -5]} intensity={0.6} color="#a78bfa" />
        <spotLight position={[0, 5, 0]} intensity={0.5} angle={0.6} penumbra={1} color="#818cf8" />
        
        <Suspense fallback={<LoadingSpinner />}>
          {!hasError ? (
            <AvatarModel avatarUrl={avatarUrl} isTalking={isTalking} />
          ) : (
            <ErrorFallback />
          )}
        </Suspense>
      </Canvas>
      
      <style>{`
        @keyframes pulse {
          0%, 100% { 
            opacity: 1;
            transform: scale(1);
          }
          50% { 
            opacity: 0.7;
            transform: scale(0.98);
          }
        }
      `}</style>
    </div>
  );
}