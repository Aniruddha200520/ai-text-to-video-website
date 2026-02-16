import React, { useState } from 'react';
import { X } from 'lucide-react';

// Local Mixamo avatars organized by style (GLB format)
const AVATAR_LIBRARY = {
  professional: [
    { id: "prof-1", name: "Business Person", url: "/models/business-avatar.glb" },
    { id: "prof-2", name: "Executive", url: "/models/executive-avatar.glb" },
    { id: "prof-3", name: "Corporate", url: "/models/corporate-avatar.glb" }
  ],
  casual: [
    { id: "cas-1", name: "Casual Guy", url: "/models/casual-avatar.glb" },
    { id: "cas-2", name: "Friendly Girl", url: "/models/friendly-avatar.glb" },
    { id: "cas-3", name: "Relaxed", url: "/models/relaxed-avatar.glb" }
  ],
  modern: [
    { id: "mod-1", name: "Modern Style", url: "/models/modern-avatar.glb" },
    { id: "mod-2", name: "Trendy", url: "/models/trendy-avatar.glb" },
    { id: "mod-3", name: "Contemporary", url: "/models/contemporary-avatar.glb" }
  ],
  animated: [
    { id: "anim-1", name: "Talking Avatar", url: "/models/talking-avatar.glb" },
    { id: "anim-2", name: "Gesturing", url: "/models/gesturing-avatar.glb" },
    { id: "anim-3", name: "Presenter", url: "/models/presenter-avatar.glb" }
  ]
};

export default function AvatarSelector({ onSelect, onClose }) {
  const [selectedCategory, setSelectedCategory] = useState('professional');
  const [selectedAvatar, setSelectedAvatar] = useState(null);
  
  const categories = [
    { id: 'professional', label: 'Professional', icon: '💼' },
    { id: 'casual', label: 'Casual', icon: '👕' },
    { id: 'modern', label: 'Modern', icon: '✨' },
    { id: 'animated', label: 'Animated', icon: '🎬' }
  ];
  
  const handleSelect = () => {
    if (selectedAvatar) {
      onSelect(selectedAvatar);
      onClose();
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl p-6 max-w-3xl w-full max-h-[85vh] overflow-y-auto border border-purple-500/30">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h3 className="text-2xl font-semibold text-white">Choose Avatar Narrator</h3>
            <p className="text-sm text-slate-400 mt-1">Mixamo 3D Characters (GLB)</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X size={24} />
          </button>
        </div>
        
        <div className="flex space-x-2 mb-6 overflow-x-auto pb-2">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-4 py-2 rounded-lg font-semibold text-sm whitespace-nowrap transition-all ${
                selectedCategory === cat.id
                  ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                  : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {cat.icon} {cat.label}
            </button>
          ))}
        </div>
        
        <div className="grid grid-cols-3 gap-4 mb-6">
          {AVATAR_LIBRARY[selectedCategory].map((avatar) => (
            <div
              key={avatar.id}
              onClick={() => setSelectedAvatar(avatar)}
              className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                selectedAvatar?.id === avatar.id
                  ? 'border-purple-500 ring-2 ring-purple-500/50'
                  : 'border-slate-600 hover:border-purple-400'
              }`}
            >
              <div className="aspect-square bg-gradient-to-br from-purple-900/30 to-pink-900/30 flex items-center justify-center">
                <div className="text-6xl">
                  {selectedCategory === 'professional' && '💼'}
                  {selectedCategory === 'casual' && '👤'}
                  {selectedCategory === 'modern' && '✨'}
                  {selectedCategory === 'animated' && '🎭'}
                </div>
              </div>
              <div className="p-3 bg-slate-900/50">
                <p className="text-sm font-semibold text-white text-center">{avatar.name}</p>
              </div>
              {selectedAvatar?.id === avatar.id && (
                <div className="absolute top-2 right-2 bg-purple-500 rounded-full p-1">
                  <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
        
        <div className="bg-blue-500/10 rounded-lg p-4 mb-6 border border-blue-500/30">
          <p className="text-sm text-blue-300 mb-2 font-semibold">
            📥 Using GLB Format
          </p>
          <p className="text-xs text-slate-400">
            GLB files from <span className="text-purple-400 font-semibold">Mixamo.com</span> → Convert FBX to GLB → Place in <code className="bg-slate-900/50 px-2 py-1 rounded">/public/models/</code>
          </p>
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={handleSelect}
            disabled={!selectedAvatar}
            className="flex-1 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 disabled:opacity-50 py-3 rounded-lg font-semibold text-white transition-all"
          >
            {selectedAvatar ? `Select ${selectedAvatar.name}` : 'Choose Avatar'}
          </button>
          <button onClick={onClose} className="px-6 py-3 bg-slate-600 hover:bg-slate-500 rounded-lg font-semibold text-white transition-all">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}