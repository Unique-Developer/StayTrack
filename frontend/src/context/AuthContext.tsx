import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User } from '../types';
import { api, getStoredToken, getStoredUser, clearStoredAuth } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Validate session on boot or when token changes
  useEffect(() => {
    let isMounted = true;

    const checkSession = async () => {
      const existingToken = getStoredToken();
      if (!existingToken) {
        if (isMounted) {
          setUser(null);
          setToken(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        const currentUser = await api.getMe();
        if (isMounted) {
          setUser(currentUser);
          setToken(existingToken);
        }
      } catch (err) {
        console.warn('Session verification failed, logging out:', err);
        clearStoredAuth();
        if (isMounted) {
          setUser(null);
          setToken(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    checkSession();

    // Listen for custom logout/unauthorized events
    const handleUnauthorized = () => {
      setUser(null);
      setToken(null);
      setIsLoading(false);
    };

    const handleLogout = () => {
      setUser(null);
      setToken(null);
      setIsLoading(false);
    };

    window.addEventListener('staytrack:unauthorized', handleUnauthorized);
    window.addEventListener('staytrack:logout', handleLogout);

    return () => {
      isMounted = false;
      window.removeEventListener('staytrack:unauthorized', handleUnauthorized);
      window.removeEventListener('staytrack:logout', handleLogout);
    };
  }, []);

  const login = async (email: string, password: string): Promise<void> => {
    const res = await api.login({ email, password });
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    api.logout();
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
