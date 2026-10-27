import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Property } from '../types';
import { api } from '../services/api';

interface PropertyContextType {
  properties: Property[];
  currentPropertyId: number;
  currentProperty: Property | null;
  setCurrentPropertyId: (id: number) => void;
  isLoading: boolean;
  refreshProperties: () => Promise<void>;
}

const PropertyContext = createContext<PropertyContextType | undefined>(undefined);

export const PropertyProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
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
    setCurrentPropertyIdState(id);
    localStorage.setItem('staytrack_property_id', String(id));
    window.dispatchEvent(new CustomEvent('staytrack:property_changed', { detail: { propertyId: id } }));
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
