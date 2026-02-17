import React, { useState, useEffect, useRef } from 'react';
import Lottie from 'lottie-react';

// REAL working Lottie animations from public CDNs
const AVATAR_ANIMATIONS = {
  business: {
    name: "Business Person",
    // Real working Lottie from LottieFiles public CDN
    url: "https://assets2.lottiefiles.com/packages/lf20_x62chJ.json"
  },
  casual: {
    name: "Casual Person", 
    // Real working Lottie - waving person
    url: "https://assets9.lottiefiles.com/packages/lf20_khzniaya.json"
  },
  robot: {
    name: "AI Robot",
    // Real working Lottie - robot assistant
    url: "https://assets4.lottiefiles.com/packages/lf20_abqysclq.json"
  }
};

export default function AnimatedAvatar({ 
  position = "bottom-right",
  size = "medium",
  avatarStyle = "business"
}) {
  const [visible, setVisible] = useState(true);
  const [isTalking, setIsTalking] = useState(false);
  const [animationData, setAnimationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const lottieRef = useRef();
  
  // Simulate talking animation
  useEffect(() => {
    const interval = setInterval(() => {
      setIsTalking(prev => !prev);
    }, 2000);
    
    return () => clearInterval(interval);
  }, []);
  
  // Control animation speed based on talking
  useEffect(() => {
    if (lottieRef.current && !loading && !error) {
      if (isTalking) {
        lottieRef.current.setSpeed(1.5);
        lottieRef.current.play();
      } else {
        lottieRef.current.setSpeed(0.5);
      }
    }
  }, [isTalking, loading, error]);
  
  // Load animation from CDN
  useEffect(() => {
    const loadAnimation = async () => {
      setLoading(true);
      setError(false);
      
      try {
        const selectedAvatar = AVATAR_ANIMATIONS[avatarStyle];
        console.log('Loading animation from:', selectedAvatar.url);
        
        const response = await fetch(selectedAvatar.url);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Animation loaded successfully!');
        setAnimationData(data);
        setError(false);
      } catch (err) {
        console.error('Failed to load animation:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    
    loadAnimation();
  }, [avatarStyle]);
  
  const positions = {
    "bottom-right": { bottom: "20px", right: "20px" },
    "bottom-left": { bottom: "20px", left: "20px" },
    "top-right": { top: "20px", right: "20px" },
    "top-left": { top: "20px", left: "20px" }
  };
  
  const sizes = {
    small: { width: "120px", height: "120px" },
    medium: { width: "180px", height: "180px" },
    large: { width: "240px", height: "240px" }
  };
  
  if (!visible) return null;
  
  return (
    <div 
      style={{
        position: "fixed",
        ...positions[position],
        ...sizes[size],
        zIndex: 9999,
        background: "linear-gradient(135deg, rgba(147, 51, 234, 0.95), rgba(79, 70, 229, 0.95))",
        borderRadius: "20px",
        border: "3px solid rgba(147, 51, 234, 0.8)",
        backdropFilter: "blur(10px)",
        boxShadow: isTalking 
          ? "0 0 40px rgba(147, 51, 234, 0.9), 0 10px 50px rgba(0, 0, 0, 0.5)"
          : "0 10px 40px rgba(0, 0, 0, 0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        transition: "all 0.3s ease",
        transform: isTalking ? "scale(1.05)" : "scale(1)"
      }}
    >
      {/* Close button */}
      <button
        onClick={() => setVisible(false)}
        style={{
          position: "absolute",
          top: "8px",
          right: "8px",
          background: "rgba(255, 255, 255, 0.2)",
          border: "none",
          borderRadius: "50%",
          width: "26px",
          height: "26px",
          cursor: "pointer",
          color: "white",
          fontSize: "16px",
          fontWeight: "bold",
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.2s"
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255, 255, 255, 0.3)"}
        onMouseLeave={(e) => e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)"}
      >
        ×
      </button>
      
      {/* Speaking indicator */}
      {isTalking && !loading && !error && (
        <div
          style={{
            position: "absolute",
            top: "-35px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(34, 197, 94, 0.2)",
            border: "2px solid rgba(34, 197, 94, 0.8)",
            borderRadius: "20px",
            padding: "5px 14px",
            fontSize: "12px",
            color: "white",
            fontWeight: "600",
            whiteSpace: "nowrap",
            animation: "pulse 1.5s ease-in-out infinite"
          }}
        >
          🎙️ Speaking
        </div>
      )}
      
      {/* Content */}
      {loading && (
        <div style={{ 
          color: 'white', 
          fontSize: '12px',
          textAlign: 'center'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            border: '4px solid rgba(255,255,255,0.3)',
            borderTop: '4px solid white',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 10px'
          }} />
          Loading...
        </div>
      )}
      
      {error && (
        <div style={{ 
          color: 'white', 
          fontSize: '48px',
          textAlign: 'center'
        }}>
          💼
        </div>
      )}
      
      {!loading && !error && animationData && (
        <Lottie
          lottieRef={lottieRef}
          animationData={animationData}
          loop={true}
          autoplay={true}
          style={{
            width: "100%",
            height: "100%",
            filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.3))"
          }}
        />
      )}
      
      <style>{`
        @keyframes pulse {
          0%, 100% { 
            opacity: 1;
            transform: translateX(-50%) scale(1);
          }
          50% { 
            opacity: 0.7;
            transform: translateX(-50%) scale(0.95);
          }
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}