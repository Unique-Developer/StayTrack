import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Property } from '../types';
import { api } from '../services/api';

interface PropertyContextType {
  properties: Property[];
  currentPropertyId: number;
  currentProperty: Property | null;
  setCurrentPropertyId: (id: number) => void;
  isLoading: boolean;
  isSwitchingProperty: boolean;
  setIsSwitchingProperty: (val: boolean) => void;
  refreshProperties: () => Promise<void>;
}

const PropertyContext = createContext<PropertyContextType | undefined>(undefined);

export const PropertyProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSwitchingProperty, setIsSwitchingProperty] = useState<boolean>(false);
  const [currentPropertyId, setCurrentPropertyIdState] = useState<number>(() => {
    const saved = localStorage.getItem('staytrack_property_id');
    return saved ? parseInt(saved, 10) : 1;
  });

  const loadProperties = async () => {
    try {
      setIsLoading(true);
      const props = await api.getProperties();
      setProperties(props);
      if (props.length > 0 && !props.some(p => p.id === currentPropertyId)) {
        setCurrentPropertyIdState(props[0].id);
        localStorage.setItem('staytrack_property_id', String(props[0].id));
      }
    } catch (err) {
      console.error('Failed to load properties:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProperties();
  }, []);

  const setCurrentPropertyId = (id: number) => {
    if (id === currentPropertyId) return;
    setIsSwitchingProperty(true);
    setCurrentPropertyIdState(id);
    localStorage.setItem('staytrack_property_id', String(id));
    window.dispatchEvent(new CustomEvent('staytrack:property_changed', { detail: { propertyId: id } }));
    // Provide a smooth visible feedback window for switching transition
    setTimeout(() => {
      setIsSwitchingProperty(false);
    }, 700);
  };

  const currentProperty = properties.find((p) => p.id === currentPropertyId) || null;

  return (
    <PropertyContext.Provider
      value={{
        properties,
        currentPropertyId,
        currentProperty,
        setCurrentPropertyId,
        isLoading,
        isSwitchingProperty,
        setIsSwitchingProperty,
        refreshProperties: loadProperties,
      }}
    >
      {children}
    </PropertyContext.Provider>
  );
};

export const useProperty = (): PropertyContextType => {
  const context = useContext(PropertyContext);
  if (!context) {
    throw new Error('useProperty must be used within a PropertyProvider');
  }
  return context;
};
