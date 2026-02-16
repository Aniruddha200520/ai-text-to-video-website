import React, { useRef, useEffect, useState, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useGLTF, useAnimations } from '@react-three/drei';

// Simple loading component
function Loader() {
  return (
    <mesh>
      <sphereGeometry args={[0.3, 16, 16]} />
      <meshStandardMaterial color="#a78bfa" wireframe />
    </mesh>
  );
}

// Avatar Model Component
function AvatarModel({ avatarUrl, isTalking }) {
  const group = useRef();
  const gltf = useGLTF(avatarUrl);
  const { actions, mixer } = useAnimations(gltf.animations, group);
  
  // Play animation when talking
  useEffect(() => {
    if (!mixer || !actions) return;
    
    const actionNames = Object.keys(actions);
    if (actionNames.length > 0) {
      const action = actions[actionNames[0]];
      if (action) {
        if (isTalking) {
          action.play();
        } else {
          action.stop();
        }
      }
    }
  }, [isTalking, actions, mixer]);
  
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
      object={gltf.scene} 
      scale={1.8}
      position={[0, -1.2, 0]}
    />
  );
}

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Avatar Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ff6b6b',
          fontSize: '12px',
          textAlign: 'center',
          padding: '20px'
        }}>
          Avatar unavailable
        </div>
      );
    }

    return this.props.children;
  }
}

// Main Avatar Narrator Component
export default function AvatarNarrator({ 
  avatarUrl = "/models/business-avatar.glb",
  position = "bottom-right",
  size = "medium"
}) {
  const [isTalking, setIsTalking] = useState(false);
  const [visible, setVisible] = useState(true);
  
  // Simulate talking (since audio detection is complex)
  useEffect(() => {
    const interval = setInterval(() => {
      setIsTalking(prev => !prev);
    }, 2000);
    
    return () => clearInterval(interval);
  }, []);
  
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
    <ErrorBoundary>
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
            justifyContent: "center"
          }}
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
              fontWeight: "600"
            }}
          >
            🎙️ Speaking
          </div>
        )}
        
        <Canvas
          camera={{ position: [0, 1.5, 3], fov: 45 }}
          style={{ width: "100%", height: "100%" }}
          gl={{ antialias: true, alpha: true }}
        >
          <ambientLight intensity={0.7} />
          <directionalLight position={[5, 5, 5]} intensity={1.2} />
          <pointLight position={[-5, 5, -5]} intensity={0.6} color="#a78bfa" />
          
          <Suspense fallback={<Loader />}>
            <AvatarModel avatarUrl={avatarUrl} isTalking={isTalking} />
          </Suspense>
        </Canvas>
      </div>
    </ErrorBoundary>
  );
}