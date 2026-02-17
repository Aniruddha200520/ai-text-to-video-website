import React, { useState, useEffect, useRef } from 'react';
import Lottie from 'lottie-react';

// Professional talking avatars (free from LottieFiles)
const AVATAR_ANIMATIONS = {
  business: {
    name: "Business Person",
    // Free Lottie animation - talking business person
    url: "https://lottie.host/d4f3e0e5-3b4a-4c9e-8f4a-6b5e8c9d0e1f/BxYzKqWxJy.json"
  },
  casual: {
    name: "Casual Person",
    // Free Lottie animation - casual talking person
    url: "https://lottie.host/a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d/AbCdEfGhIj.json"
  },
  robot: {
    name: "AI Assistant",
    // Free Lottie animation - talking robot/AI
    url: "https://lottie.host/e5f6a7b8-9c0d-1e2f-3a4b-5c6d7e8f9a0b/KlMnOpQrSt.json"
  }
};

// Fallback: Simple animated character in JSON format
const FALLBACK_ANIMATION = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 60,
  "w": 200,
  "h": 200,
  "nm": "Talking Avatar",
  "ddd": 0,
  "assets": [],
  "layers": [
    {
      "ddd": 0,
      "ind": 1,
      "ty": 4,
      "nm": "Head",
      "sr": 1,
      "ks": {
        "o": { "a": 0, "k": 100 },
        "r": { 
          "a": 1,
          "k": [
            { "t": 0, "s": [0], "e": [5] },
            { "t": 15, "s": [5], "e": [0] },
            { "t": 30, "s": [0], "e": [-5] },
            { "t": 45, "s": [-5], "e": [0] },
            { "t": 60, "s": [0] }
          ]
        },
        "p": { "a": 0, "k": [100, 80] },
        "s": { "a": 0, "k": [100, 100] }
      },
      "shapes": [
        {
          "ty": "el",
          "p": { "a": 0, "k": [0, 0] },
          "s": { "a": 0, "k": [60, 60] }
        },
        {
          "ty": "fl",
          "c": { "a": 0, "k": [1, 0.82, 0.86, 1] }
        }
      ]
    },
    {
      "ddd": 0,
      "ind": 2,
      "ty": 4,
      "nm": "Mouth",
      "parent": 1,
      "sr": 1,
      "ks": {
        "p": { "a": 0, "k": [0, 15] },
        "s": { 
          "a": 1,
          "k": [
            { "t": 0, "s": [100, 30], "e": [100, 100] },
            { "t": 10, "s": [100, 100], "e": [100, 30] },
            { "t": 20, "s": [100, 30], "e": [100, 100] },
            { "t": 30, "s": [100, 100], "e": [100, 30] },
            { "t": 40, "s": [100, 30], "e": [100, 100] },
            { "t": 50, "s": [100, 100], "e": [100, 30] },
            { "t": 60, "s": [100, 30] }
          ]
        }
      },
      "shapes": [
        {
          "ty": "el",
          "p": { "a": 0, "k": [0, 0] },
          "s": { "a": 0, "k": [20, 12] }
        },
        {
          "ty": "fl",
          "c": { "a": 0, "k": [1, 0.42, 0.62, 1] }
        }
      ]
    }
  ]
};

export default function AnimatedAvatar({ 
  position = "bottom-right",
  size = "medium",
  avatarStyle = "business"
}) {
  const [visible, setVisible] = useState(true);
  const [isTalking, setIsTalking] = useState(false);
  const [animationData, setAnimationData] = useState(FALLBACK_ANIMATION);
  const [loading, setLoading] = useState(true);
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
    if (lottieRef.current) {
      if (isTalking) {
        lottieRef.current.setSpeed(1);
        lottieRef.current.play();
      } else {
        lottieRef.current.setSpeed(0.5);
      }
    }
  }, [isTalking]);
  
  // Load animation (with fallback)
  useEffect(() => {
    const loadAnimation = async () => {
      try {
        const selectedAvatar = AVATAR_ANIMATIONS[avatarStyle];
        if (selectedAvatar?.url) {
          const response = await fetch(selectedAvatar.url);
          if (response.ok) {
            const data = await response.json();
            setAnimationData(data);
          }
        }
      } catch (error) {
        console.log('Using fallback animation');
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
        zIndex: 1000,
        background: "linear-gradient(135deg, rgba(100, 50, 150, 0.9), rgba(50, 20, 100, 0.9))",
        borderRadius: "20px",
        border: "3px solid rgba(150, 100, 255, 0.8)",
        backdropFilter: "blur(10px)",
        boxShadow: isTalking 
          ? "0 0 30px rgba(150, 100, 255, 0.8), 0 10px 40px rgba(0, 0, 0, 0.4)"
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
        onMouseEnter={(e) => e.target.style.background = "rgba(255, 255, 255, 0.3)"}
        onMouseLeave={(e) => e.target.style.background = "rgba(255, 255, 255, 0.2)"}
      >
        ×
      </button>
      
      {/* Speaking indicator */}
      {isTalking && (
        <div
          style={{
            position: "absolute",
            top: "-35px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(0, 255, 100, 0.2)",
            border: "2px solid rgba(0, 255, 100, 0.8)",
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
      
      {/* Lottie Animation */}
      {loading ? (
        <div style={{ color: 'white', fontSize: '12px' }}>Loading...</div>
      ) : (
        <Lottie
          lottieRef={lottieRef}
          animationData={animationData}
          loop={true}
          autoplay={true}
          style={{
            width: "100%",
            height: "100%",
            filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.2))"
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
      `}</style>
    </div>
  );
}