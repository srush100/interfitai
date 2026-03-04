import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '../services/api';

interface UserProfile {
  id: string;
  name: string;
  email: string;
  weight: number;
  height: number;
  age: number;
  gender: string;
  activity_level: string;
  goal: string;
  calculated_macros: {
    calories: number;
    protein: number;
    carbs: number;
    fats: number;
    bmr: number;
    tdee: number;
  } | null;
  subscription_status: string;
  subscription_end_date: string | null;
  reminders_enabled: boolean;
  motivation_enabled: boolean;
}

interface UserState {
  profile: UserProfile | null;
  isOnboarded: boolean;
  isLoading: boolean;
  error: string | null;
  loadProfile: () => Promise<void>;
  createProfile: (data: Partial<UserProfile>) => Promise<void>;
  updateProfile: (data: Partial<UserProfile>) => Promise<void>;
  setOnboarded: (value: boolean) => Promise<void>;
}

export const useUserStore = create<UserState>((set, get) => ({
  profile: null,
  isOnboarded: false,
  isLoading: false,
  error: null,

  loadProfile: async () => {
    try {
      const userId = await AsyncStorage.getItem('userId');
      const onboarded = await AsyncStorage.getItem('isOnboarded');
      
      set({ isOnboarded: onboarded === 'true' });
      
      if (userId) {
        const response = await api.get(`/profile/${userId}`);
        set({ profile: response.data });
      }
    } catch (error) {
      console.log('No existing profile found');
    }
  },

  createProfile: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post('/profile', data);
      const profile = response.data;
      await AsyncStorage.setItem('userId', profile.id);
      await AsyncStorage.setItem('isOnboarded', 'true');
      set({ profile, isOnboarded: true, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },

  updateProfile: async (data) => {
    const { profile } = get();
    if (!profile) return;
    
    set({ isLoading: true, error: null });
    try {
      const response = await api.put(`/profile/${profile.id}`, data);
      set({ profile: response.data, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },

  setOnboarded: async (value) => {
    await AsyncStorage.setItem('isOnboarded', value.toString());
    set({ isOnboarded: value });
  },
}));