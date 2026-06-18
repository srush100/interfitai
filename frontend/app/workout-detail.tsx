import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  ActivityIndicator,
  Image,
  TextInput,
  Modal,
  Alert,
  ScrollView,
  Platform,
  Animated,
  ActionSheetIOS,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import * as ImagePicker from 'expo-image-picker';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';
import * as Haptics from 'expo-haptics';
import { useUserStore } from '../src/store/userStore';

// Get backend URL for constructing full GIF URLs
const BACKEND_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || 
                    process.env.EXPO_PUBLIC_BACKEND_URL || 
                    'https://nutrition-debug-1.preview.emergentagent.com';

// Helper to get full GIF URL
const getFullGifUrl = (gifUrl: string | undefined) => {
  if (!gifUrl) return null;
  if (gifUrl.startsWith('http')) return gifUrl;
  return `${BACKEND_URL}${gifUrl}`;
};

interface Exercise {
  name: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  instructions: string;
  muscle_groups: string[];
  equipment: string;
  gif_url?: string;
  effort_target?: string;    // e.g. "RIR 2-3", "RPE 8-9"
  exercise_type?: string;    // primary_compound / isolation / etc.
  substitution_hint?: string;
}

interface ExercisePerformance {
  weight: string;
  reps: string;
  completed: boolean;
}

interface WorkoutDay {
  day: string;
  focus: string;
  exercises: Exercise[];
  duration_minutes: number;
  notes: string;
}

interface WeekProgression {
  week: number;
  label: string;
  instruction: string;
}

interface WorkoutProgram {
  id: string;
  name: string;
  goal: string;
  training_style?: string;
  fitness_level?: string;
  focus_areas: string[];
  secondary_focus_areas?: string[];
  equipment: string[];
  days_per_week: number;
  workout_days: WorkoutDay[];
  created_at: string;
  // Coaching metadata (from elite coaching engine)
  split_name?: string;
  split_rationale?: string;
  progression_method?: string;
  deload_timing?: string;
  weekly_structure?: string[];
  weekly_progression?: WeekProgression[];
  current_week_override?: number | null;
  training_notes?: string;
}

// ─── Confetti burst (PR celebration) ────────────────────────────────────────
const CONFETTI_PALETTE = ['#FFD700','#FFC300','#FF9500','#FFECB3','#FF6B6B','#87CEEB','#98FB98'];
const CONFETTI_PIECES = Array.from({ length: 26 }, (_, i) => ({
  id: i,
  color: CONFETTI_PALETTE[i % CONFETTI_PALETTE.length],
  leftPct: `${Math.round(2 + (i / 25) * 93 + Math.sin(i * 2.39) * 4)}%`,
  delay: (i % 7) * 110,
  w: 7 + (i % 4) * 2,
}));

const ConfettiPiece = React.memo(function ConfettiPiece({ color, leftPct, delay, w }: {
  color: string; leftPct: string; delay: number; w: number;
}) {
  const y = useRef(new Animated.Value(0)).current;
  const alpha = useRef(new Animated.Value(0)).current;
  const rot = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const anim = Animated.sequence([
      Animated.delay(delay),
      Animated.parallel([
        Animated.timing(alpha, { toValue: 1, duration: 80, useNativeDriver: false }),
        Animated.timing(y,     { toValue: 620, duration: 2400, useNativeDriver: false }),
        Animated.timing(rot,   { toValue: 8,   duration: 2400, useNativeDriver: false }),
        Animated.sequence([
          Animated.delay(1600),
          Animated.timing(alpha, { toValue: 0, duration: 800, useNativeDriver: false }),
        ]),
      ]),
    ]);
    anim.start();
    return () => anim.stop();
  }, []);

  const rotate = rot.interpolate({ inputRange: [0, 8], outputRange: ['0deg', '1440deg'] });

  return (
    <Animated.View style={{
      position: 'absolute',
      left: leftPct,
      top: -14,
      width: w,
      height: w / 2,
      backgroundColor: color,
      borderRadius: 2,
      opacity: alpha,
      transform: [{ translateY: y }, { rotate }],
    }} />
  );
});

const ConfettiBurst = ({ active }: { active: boolean }) => {
  if (!active) return null;
  return (
    <View
      style={StyleSheet.absoluteFill}
      pointerEvents="none"
      collapsable={false}
    >
      {CONFETTI_PIECES.map(p => (
        <ConfettiPiece key={p.id} color={p.color} leftPct={p.leftPct} delay={p.delay} w={p.w} />
      ))}
    </View>
  );
};
// ────────────────────────────────────────────────────────────────────────────

export default function WorkoutDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { profile, updateProfile } = useUserStore();

  // Unit preference — local state for optimistic updates + inline toggle
  const [localUnit, setLocalUnit] = useState<'kg' | 'lbs'>(
    (profile?.unit_preference as 'kg' | 'lbs') || 'kg'
  );
  const kgToDisplay = (kg: number) =>
    localUnit === 'lbs' ? Math.round(kg * 2.20462 * 10) / 10 : kg;
  const displayToKg = (val: number) =>
    localUnit === 'lbs' ? val / 2.20462 : val;  // full precision — rounded only for display
  const [workout, setWorkout] = useState<WorkoutProgram | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedDay, setExpandedDay] = useState<number>(0);
  const [expandedExercise, setExpandedExercise] = useState<string | null>(null);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [renaming, setRenaming] = useState(false);
  // Performance tracking state
  const [performance, setPerformance] = useState<Record<string, ExercisePerformance>>({});
  const [saving, setSaving] = useState(false);
  // Exercise replacement/add state
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<{dayIdx: number, exIdx: number} | null>(null);
  const [isAddMode, setIsAddMode] = useState(false);
  const [addToDayIdx, setAddToDayIdx] = useState<number | null>(null);
  // Drag-to-reorder state
  const [reordering, setReordering] = useState(false);
  const [selectedExIdx, setSelectedExIdx] = useState<number | null>(null);
  const swapPulse = useRef(new Animated.Value(0)).current;
  const swapPulseAnim = useRef<Animated.CompositeAnimation | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedMuscle, setSelectedMuscle] = useState<string | null>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Pagination state for exercise search
  const [exerciseOffset, setExerciseOffset] = useState(0);
  const [exerciseTotalCount, setExerciseTotalCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  // ── Session history state ─────────────────────────────────────────────────
  const [lastSession, setLastSession] = useState<Record<number, any>>({});
  const [sessionStartTime, setSessionStartTime] = useState<Date | null>(null);
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [completedSessionData, setCompletedSessionData] = useState<{
    volume: number;
    duration: number | null;
    personal_records: Array<{ exercise_name: string; type: string; new_value: number; previous_value: number | null; reps: number }>;
    session_id: string;
    current_streak: number;
  } | null>(null);
  const [finishing, setFinishing] = useState(false);
  // Post-workout photo
  const [sessionPhotoUri, setSessionPhotoUri] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [showPhotoPickerModal, setShowPhotoPickerModal] = useState(false);

  // Muscle groups with icons and emoji for professional visual UI
  const muscleGroups = [
    { id: 'chest', label: 'Chest', icon: 'fitness-outline', emoji: '💪' },
    { id: 'back', label: 'Back', icon: 'body-outline', emoji: '🦴' },
    { id: 'shoulders', label: 'Shoulders', icon: 'ellipse-outline', emoji: '🎯' },
    { id: 'biceps', label: 'Biceps', icon: 'barbell-outline', emoji: '💪' },
    { id: 'triceps', label: 'Triceps', icon: 'barbell-outline', emoji: '🔱' },
    { id: 'legs', label: 'Legs', icon: 'walk-outline', emoji: '🦵' },
    { id: 'glutes', label: 'Glutes', icon: 'accessibility-outline', emoji: '🍑' },
    { id: 'abs', label: 'Core', icon: 'grid-outline', emoji: '🧱' },
    { id: 'cardio', label: 'Cardio', icon: 'heart-outline', emoji: '❤️' },
  ];

  useEffect(() => {
    loadWorkout();
  }, [id]);

  const loadWorkout = async () => {
    try {
      const response = await api.get(`/workout/${id}`);
      setWorkout(response.data);
      setNewName(response.data.name);
      
      // Load saved performance data
      try {
        const perfResponse = await api.get(`/workout/${id}/performance`);
        if (perfResponse.data.performance) {
          setPerformance(perfResponse.data.performance);
        }
      } catch (perfError) {
        console.log('No saved performance data');
      }
    } catch (error) {
      console.log('Error loading workout:', error);
    } finally {
      setLoading(false);
    }
  };

  // Auto-save performance when it changes
  const savePerformance = async (newPerformance: Record<string, ExercisePerformance>) => {
    if (!workout) return;
    try {
      await api.post(`/workout/${workout.id}/performance`, { performance: newPerformance });
    } catch (error) {
      console.log('Error saving performance:', error);
    }
  };

  // Update performance and auto-save
  const updatePerformance = (key: string, data: ExercisePerformance) => {
    const newPerformance = { ...performance, [key]: data };
    setPerformance(newPerformance);
    // Start session timer on first interaction with this day
    if (!sessionStartTime) {
      setSessionStartTime(new Date());
    }
    // Auto-save when checkbox is checked
    if (data.completed) {
      savePerformance(newPerformance);
    }
  };

  // ── Session history functions ──────────────────────────────────────────────

  const loadLastSession = async (dayIdx: number) => {
    if (!id) return;
    try {
      const response = await api.get(`/workout/${id}/last-session`, {
        params: { day_index: dayIdx },
      });
      if (response.data) {
        setLastSession(prev => ({ ...prev, [dayIdx]: response.data }));
      }
    } catch {
      // No previous session — that's fine
    }
  };

  // Load last session when day tab switches
  useEffect(() => {
    if (workout) {
      loadLastSession(expandedDay);
      // Reset timer when switching days
      setSessionStartTime(new Date());
    }
  }, [expandedDay, workout?.id]);

  // Sync localUnit when profile preference changes (e.g. changed from profile screen)
  useEffect(() => {
    if (profile?.unit_preference) {
      setLocalUnit(profile.unit_preference as 'kg' | 'lbs');
    }
  }, [profile?.unit_preference]);

  // Reset swap mode when the user switches workout days
  useEffect(() => {
    setSelectedExIdx(null);
    longPressActive.current = false;
  }, [expandedDay]);

  // Toggle unit inline — converts entered values + persists globally
  const toggleLocalUnit = async () => {
    const newUnit = localUnit === 'kg' ? 'lbs' : 'kg';
    // Convert any already-entered weight values optimistically
    const converted: Record<string, ExercisePerformance> = {};
    Object.entries(performance).forEach(([key, perf]) => {
      if (perf.weight) {
        const val = parseFloat(perf.weight);
        if (!isNaN(val) && val > 0) {
          const newVal =
            newUnit === 'lbs'
              ? Math.round(val * 2.20462 * 10) / 10  // kg → lbs
              : Math.round((val / 2.20462) * 10) / 10; // lbs → kg
          converted[key] = { ...perf, weight: String(newVal) };
        } else {
          converted[key] = perf;
        }
      } else {
        converted[key] = perf;
      }
    });
    setLocalUnit(newUnit);
    setPerformance(converted);
    try {
      await updateProfile({ unit_preference: newUnit });
    } catch {
      // silent — optimistic update already applied
    }
  };

  // Get "last time" hint text for a specific set
  const getLastTimeHint = (dayIdx: number, exIdx: number, setIdx: number): string | null => {
    const session = lastSession[dayIdx];
    if (!session) return null;
    const ex = session.completed_exercises?.[exIdx];
    if (!ex) return null;
    const set = ex.sets?.[setIdx];
    if (!set || !set.completed) return null;
    if (set.weight && set.reps) return `${kgToDisplay(set.weight)}${localUnit} × ${set.reps}`;
    if (set.reps) return `${set.reps} reps`;
    return null;
  };

  const handleFinishWorkout = async () => {
    if (!workout || !profile?.id) return;
    setFinishing(true);

    const day = workout.workout_days[expandedDay];

    // Build completed_exercises from current performance state
    const completed_exercises = day.exercises.map((exercise: any, exIdx: number) => ({
      exercise_name: exercise.name,
      muscle_groups: exercise.muscle_groups || [],
      sets: Array.from({ length: exercise.sets }, (_, setIdx) => {
        const key = `${expandedDay}-${exIdx}-${setIdx}`;
        const perf = performance[key] || { weight: '', reps: '', completed: false };
        return {
          set_number: setIdx + 1,
          weight: perf.weight ? displayToKg(parseFloat(perf.weight)) : null,
          reps: perf.reps ? parseInt(perf.reps) : null,
          completed: perf.completed,
        };
      }),
    }));

    const durationMinutes = sessionStartTime
      ? Math.max(1, Math.round((Date.now() - sessionStartTime.getTime()) / 60000))
      : null;

    try {
      const response = await api.post(`/workout/${workout.id}/session/complete`, {
        user_id: profile.id,
        day_index: expandedDay,
        day_focus: day.focus || '',
        duration_minutes: durationMinutes,
        completed_exercises,
      });

      const prs: any[] = response.data.personal_records || [];
      const hasPR = prs.length > 0;

      // Fetch current streak
      let currentStreak = 0;
      try {
        const statsRes = await api.get(`/workout/stats/${profile.id}`);
        currentStreak = statsRes.data.current_streak || 0;
      } catch {
        // streak is non-critical
      }

      // Fire haptics — double pulse for a PR
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      if (hasPR) {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      }

      setSessionPhotoUri(null);
      setCompletedSessionData({
        volume: response.data.total_volume,
        duration: durationMinutes,
        personal_records: prs,
        session_id: response.data.id,
        current_streak: currentStreak,
      });
      setShowCompleteModal(true);
      // Update cached last session so "last time" hints refresh immediately
      setLastSession(prev => ({ ...prev, [expandedDay]: response.data }));
      // Blank slate: fully clear weight, reps, and checkboxes for this day
      // (backend also persists this server-side so it survives reloads)
      const clearedPerformance = { ...performance };
      Object.keys(clearedPerformance).forEach(key => {
        if (key.startsWith(`${expandedDay}-`)) {
          clearedPerformance[key] = { weight: '', reps: '', completed: false };
        }
      });
      setPerformance(clearedPerformance);
      savePerformance(clearedPerformance);
      setSessionStartTime(new Date()); // reset timer for a potential second session
    } catch (error) {
      console.log('Error completing session:', error);
      Alert.alert('Error', 'Could not save your session. Please try again.');
    } finally {
      setFinishing(false);
    }
  };

  // Shared photo upload helper
  const uploadPhotoResult = async (asset: { base64: string | null | undefined; uri: string }) => {
    if (!asset.base64 || !completedSessionData?.session_id) return;
    setPhotoUploading(true);
    try {
      await api.post(`/workout/session/${completedSessionData.session_id}/photo`, {
        photo_base64: asset.base64,
      });
      setSessionPhotoUri(asset.uri);
    } catch {
      Alert.alert('Error', 'Could not save photo. You can add one later.');
    } finally {
      setPhotoUploading(false);
    }
  };

  const handleTakePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Camera access needed', 'Allow camera access to take a workout photo.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.6,
      base64: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    await uploadPhotoResult(result.assets[0]);
  };

  const handleChooseFromLibrary = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Allow access to your photo library to add a workout photo.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.6,
      base64: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    await uploadPhotoResult(result.assets[0]);
  };

  const handleAddPhoto = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        { options: ['Cancel', 'Take Photo', 'Choose from Library'], cancelButtonIndex: 0 },
        (index) => {
          if (index === 1) handleTakePhoto();
          else if (index === 2) handleChooseFromLibrary();
        }
      );
    } else {
      setShowPhotoPickerModal(true);
    }
  };

  const handleRename = async () => {
    if (!newName.trim() || !workout) return;
    
    setRenaming(true);
    try {
      await api.patch(`/workout/${workout.id}/rename`, { name: newName.trim() });
      setWorkout({ ...workout, name: newName.trim() });
      setShowRenameModal(false);
      Alert.alert('Success', 'Workout renamed successfully');
    } catch (error) {
      Alert.alert('Error', 'Failed to rename workout');
    } finally {
      setRenaming(false);
    }
  };

  // Add extra set to an exercise
  const addSet = async (dayIdx: number, exIdx: number) => {
    if (!workout) return;
    const newWorkout = { ...workout };
    const exercise = newWorkout.workout_days[dayIdx].exercises[exIdx];
    exercise.sets += 1;
    
    try {
      await api.patch(`/workout/${workout.id}/exercise`, {
        day_index: dayIdx,
        exercise_index: exIdx,
        sets: exercise.sets,
      });
      setWorkout(newWorkout);
    } catch (error) {
      Alert.alert('Error', 'Failed to add set');
    }
  };

  // Remove a set from an exercise
  const removeSet = async (dayIdx: number, exIdx: number) => {
    if (!workout) return;
    const exercise = workout.workout_days[dayIdx].exercises[exIdx];
    if (exercise.sets <= 1) {
      Alert.alert('Cannot Remove', 'Exercise must have at least 1 set');
      return;
    }
    
    const newWorkout = { ...workout };
    newWorkout.workout_days[dayIdx].exercises[exIdx].sets -= 1;
    
    try {
      await api.patch(`/workout/${workout.id}/exercise`, {
        day_index: dayIdx,
        exercise_index: exIdx,
        sets: newWorkout.workout_days[dayIdx].exercises[exIdx].sets,
      });
      setWorkout(newWorkout);
    } catch (error) {
      Alert.alert('Error', 'Failed to remove set');
    }
  };

  // Add manual exercise (user-typed)
  const addManualExercise = async () => {
    if (!searchQuery.trim() || !workout) return;
    
    const manualExercise = {
      name: searchQuery.trim(),
      sets: 3,
      reps: '10-12',
      rest_seconds: 90,
      instructions: 'Perform the exercise with proper form.',
      muscle_groups: [selectedMuscle || 'general'],
      equipment: 'varies',
      gif_url: '',  // Backend will try to fetch GIF
    };
    
    if (isAddMode && addToDayIdx !== null) {
      // Add mode - add new exercise
      try {
        await api.post(`/workout/${workout.id}/exercise`, {
          day_index: addToDayIdx,
          exercise: manualExercise,
        });
        
        setShowReplaceModal(false);
        setIsAddMode(false);
        setAddToDayIdx(null);
        setSearchQuery('');
        setSearchResults([]);
        setSelectedMuscle(null);
        loadWorkout();
      } catch (error) {
        Alert.alert('Error', 'Failed to add exercise');
      }
    } else if (replaceTarget) {
      // Replace mode - replace existing exercise
      const { dayIdx, exIdx } = replaceTarget;
      const currentEx = workout.workout_days[dayIdx].exercises[exIdx];
      manualExercise.sets = currentEx.sets;
      manualExercise.reps = currentEx.reps;
      manualExercise.rest_seconds = currentEx.rest_seconds;
      replaceWithExercise(manualExercise);
    }
  };

  // Replace with selected exercise
  const replaceWithExercise = async (newExercise: any) => {
    if (!workout || !replaceTarget) return;
    const { dayIdx, exIdx } = replaceTarget;
    
    try {
      await api.patch(`/workout/${workout.id}/replace-exercise`, {
        day_index: dayIdx,
        exercise_index: exIdx,
        new_exercise: newExercise,
      });
      
      loadWorkout();
      setShowReplaceModal(false);
      setReplaceTarget(null);
      setSearchQuery('');
      setSearchResults([]);
      setSelectedMuscle(null);
      Alert.alert('Success', 'Exercise replaced!');
    } catch (error) {
      Alert.alert('Error', 'Failed to replace exercise');
    }
  };

  // Maps ANY muscle name (ExerciseDB target OR backend label) to a chip ID
  const getMuscleChipForTarget = (target: string): string | null => {
    const t = target?.toLowerCase().trim() || '';
    // ExerciseDB exact target values
    const exactMap: Record<string, string> = {
      pectorals: 'chest',
      lats: 'back', 'upper back': 'back', 'lower back': 'back', traps: 'back', spine: 'back',
      'serratus anterior': 'back', rhomboids: 'back', levator: 'back',
      delts: 'shoulders', deltoids: 'shoulders',
      biceps: 'biceps', brachialis: 'biceps', brachioradialis: 'biceps',
      triceps: 'triceps',
      quads: 'legs', hamstrings: 'legs', calves: 'legs', adductors: 'legs', abductors: 'legs',
      glutes: 'glutes',
      abs: 'abs', obliques: 'abs', core: 'abs',
      'cardiovascular system': 'cardio', cardio: 'cardio',
      // Backend-specific labels
      chest: 'chest', 'upper chest': 'chest', 'lower chest': 'chest',
      'inner chest': 'chest', 'outer chest': 'chest',
      shoulders: 'shoulders', 'front delts': 'shoulders', 'side delts': 'shoulders',
      'rear delts': 'back', 'rear deltoid': 'back',
      'glute max': 'glutes', 'glute med': 'glutes',
    };
    if (exactMap[t]) return exactMap[t];
    // Partial keyword matches for composite labels
    if (t.includes('chest') || t.includes('pectoral')) return 'chest';
    if (t.includes('lats') || t.includes('back') || t.includes('rhomboid') || t.includes('trap')) return 'back';
    if (t.includes('delt') || t.includes('shoulder')) return 'shoulders';
    if (t.includes('bicep') || t.includes('brachial')) return 'biceps';
    if (t.includes('tricep')) return 'triceps';
    if (t.includes('quad') || t.includes('hamstring') || t.includes('calf') || t.includes('calves') || t.includes('leg')) return 'legs';
    if (t.includes('glute')) return 'glutes';
    if (t.includes('abs') || t.includes('core') || t.includes('oblique') || t.includes('waist')) return 'abs';
    if (t.includes('cardio') || t.includes('cardiovascular')) return 'cardio';
    return null;
  };

  // Search exercises from local MongoDB (no rate limits)
  const searchExercises = async (query: string, muscle?: string, appendResults = false, offset = 0) => {
    if (!appendResults) {
      setSearching(true);
      setExerciseOffset(0);
    } else {
      setLoadingMore(true);
    }
    try {
      const params = new URLSearchParams();
      if (query) params.append('search', query);
      if (muscle) params.append('muscle', muscle);
      params.append('limit', '50');
      params.append('offset', offset.toString());

      const response = await api.get(`/exercises/search?${params.toString()}`);
      const newResults: any[] = response.data.exercises || [];
      const total: number = response.data.total_count || 0;

      if (appendResults) {
        setSearchResults(prev => [...prev, ...newResults]);
        setExerciseOffset(offset + newResults.length);
      } else {
        setSearchResults(newResults);
        setExerciseOffset(newResults.length);
      }
      setExerciseTotalCount(total);
    } catch (error) {
      console.log('Search error:', error);
      if (!appendResults) setSearchResults([]);
    } finally {
      if (!appendResults) setSearching(false);
      else setLoadingMore(false);
    }
  };

  // Debounced search — always resets to page 1 (offset 0)
  const debouncedSearch = useCallback((query: string, muscle?: string) => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    setSearching(true);
    searchTimeoutRef.current = setTimeout(() => {
      searchExercises(query, muscle, false, 0);
    }, 400);
  }, []);

  // Replace an exercise with one from search results
  const replaceExercise = async (newExercise: any) => {
    if (!workout || !replaceTarget) return;
    const { dayIdx, exIdx } = replaceTarget;
    const currentEx = workout.workout_days[dayIdx].exercises[exIdx];
    
    const exerciseData = {
      name: newExercise.name,
      sets: currentEx.sets,
      reps: currentEx.reps,
      rest_seconds: currentEx.rest_seconds,
      instructions: newExercise.instructions?.join(' ') || 'Perform with proper form.',
      muscle_groups: [newExercise.target, ...(newExercise.secondaryMuscles || [])],
      equipment: newExercise.equipment,
      gif_url: newExercise.gifUrl || '',
    };
    
    await replaceWithExercise(exerciseData);
  };

  // Delete an exercise
  const deleteExercise = async (dayIdx: number, exIdx: number) => {
    Alert.alert(
      'Delete Exercise',
      'Are you sure you want to remove this exercise?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/workout/${workout?.id}/exercise`, {
                data: { day_index: dayIdx, exercise_index: exIdx },
              });
              loadWorkout();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete exercise');
            }
          },
        },
      ]
    );
  };

  // Add a new exercise to a day
  const addExerciseToDay = async (newExercise: any) => {
    if (!workout || addToDayIdx === null) return;
    
    try {
      const exerciseData = {
        name: newExercise.name,
        sets: 3,
        reps: '10-12',
        rest_seconds: 90,
        instructions: newExercise.instructions?.join(' ') || 'Perform with proper form and controlled movements.',
        muscle_groups: [newExercise.target, ...(newExercise.secondaryMuscles || [])],
        equipment: newExercise.equipment,
        gif_url: newExercise.gifUrl || '',
      };
      
      await api.post(`/workout/${workout.id}/exercise`, {
        day_index: addToDayIdx,
        exercise: exerciseData,
      });
      
      // Close modal and reload
      setShowReplaceModal(false);
      setIsAddMode(false);
      setAddToDayIdx(null);
      setSearchQuery('');
      setSearchResults([]);
      setSelectedMuscle(null);
      loadWorkout();
    } catch (error) {
      Alert.alert('Error', 'Failed to add exercise');
    }
  };

  // Handle exercise selection in modal (either replace or add)
  const handleExerciseSelect = (exercise: any) => {
    if (isAddMode) {
      addExerciseToDay(exercise);
    } else {
      replaceExercise(exercise);
    }
  };

  // Pulse animation when an exercise is selected for swapping
  useEffect(() => {
    if (selectedExIdx !== null) {
      swapPulseAnim.current = Animated.loop(
        Animated.sequence([
          Animated.timing(swapPulse, { toValue: 1, duration: 700, useNativeDriver: true }),
          Animated.timing(swapPulse, { toValue: 0.3, duration: 700, useNativeDriver: true }),
        ])
      );
      swapPulse.setValue(0.3);
      swapPulseAnim.current.start();
    } else {
      swapPulseAnim.current?.stop();
      swapPulse.setValue(0);
    }
  }, [selectedExIdx]);

  // Ref guard: prevents onPress from firing right after onLongPress (React Native Web fires both)
  const longPressActive = useRef(false);

  // Long press to select exercise for swapping
  const handleExerciseLongPress = (exIdx: number) => {
    longPressActive.current = true;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setSelectedExIdx(exIdx);
    setExpandedExercise(null); // collapse detail when entering swap mode
  };

  // Tap handler: if in swap mode, swap or deselect; otherwise expand/collapse
  const handleExerciseTap = (exIdx: number) => {
    // Suppress the onPress that React Native fires immediately after onLongPress
    if (longPressActive.current) {
      longPressActive.current = false;
      return;
    }
    if (selectedExIdx !== null) {
      if (selectedExIdx === exIdx) {
        // Tap same card → cancel
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setSelectedExIdx(null);
      } else {
        // Tap different card → swap
        swapExercises(selectedExIdx, exIdx);
      }
    } else {
      setExpandedExercise(
        expandedExercise === `${expandedDay}-${exIdx}` ? null : `${expandedDay}-${exIdx}`
      );
    }
  };

  // Swap two exercises and persist
  const swapExercises = useCallback(async (fromIdx: number, toIdx: number) => {
    if (!workout) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setSelectedExIdx(null);

    const originalExercises = workout.workout_days[expandedDay].exercises;
    const newExercises = [...originalExercises];
    [newExercises[fromIdx], newExercises[toIdx]] = [newExercises[toIdx], newExercises[fromIdx]];

    const updatedDays = workout.workout_days.map((day, i) =>
      i === expandedDay ? { ...day, exercises: newExercises } : day
    );
    setWorkout({ ...workout, workout_days: updatedDays });

    try {
      const newOrder = newExercises.map((ex) =>
        originalExercises.findIndex((o) => o.name === ex.name)
      );
      await api.patch(`/workout/${workout.id}/reorder-exercises`, {
        day_index: expandedDay,
        exercise_order: newOrder,
      });
    } catch (e) {
      // silent — local state is correct
    }
  }, [workout, expandedDay]);



  // Open modal in add mode
  const openAddExerciseModal = (dayIdx: number) => {
    setIsAddMode(true);
    setAddToDayIdx(dayIdx);
    setReplaceTarget(null);
    setShowReplaceModal(true);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedMuscle(null);
    setExerciseOffset(0);
    setExerciseTotalCount(0);
  };

  // Open modal in replace mode — muscle pre-selection is handled by the effect below
  const openReplaceExerciseModal = (dayIdx: number, exIdx: number) => {
    setIsAddMode(false);
    setReplaceTarget({ dayIdx, exIdx });
    setAddToDayIdx(null);
    setShowReplaceModal(true);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedMuscle(null);
    setExerciseOffset(0);
    setExerciseTotalCount(0);
  };

  // Auto-load exercises and pre-select muscle chip when the modal opens in replace mode
  // Using workout in deps ensures we have the latest exercise data available
  useEffect(() => {
    if (!showReplaceModal) return;
    if (isAddMode) {
      // Add mode: just load the full library
      searchExercises('', undefined);
      return;
    }
    if (!replaceTarget || !workout) return;
    const { dayIdx, exIdx } = replaceTarget;
    const currentEx = workout.workout_days[dayIdx]?.exercises[exIdx];
    const primaryTarget = (currentEx?.muscle_groups?.[0] || '').toLowerCase().trim();
    const CHIP_IDS = ['chest', 'back', 'shoulders', 'biceps', 'triceps', 'legs', 'glutes', 'abs', 'cardio'];
    const chipId = CHIP_IDS.includes(primaryTarget)
      ? primaryTarget
      : getMuscleChipForTarget(primaryTarget);
    if (chipId) {
      setSelectedMuscle(chipId);
      searchExercises('', chipId);
    } else {
      searchExercises('', undefined);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showReplaceModal, isAddMode, replaceTarget, workout]);

  // Refresh GIF URLs for all exercises
  const [refreshingGifs, setRefreshingGifs] = useState(false);
  // Week progression modal
  const [showWeekModal, setShowWeekModal] = useState(false);

  // ── Compute current week (auto from created_at, or from manual override) ──
  const currentWeek = useMemo(() => {
    if (!workout) return 1;
    if (workout.current_week_override != null) return workout.current_week_override;
    const createdAt = new Date(workout.created_at);
    const daysDiff = Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60 * 24));
    return Math.min(12, Math.floor(daysDiff / 7) + 1);
  }, [workout]);
  
  const refreshGifs = async () => {
    if (!workout) return;
    setRefreshingGifs(true);
    try {
      await api.post(`/workout/${workout.id}/refresh-gifs`);
      await loadWorkout();
      Alert.alert('Success', 'Exercise images have been refreshed!');
    } catch (error) {
      Alert.alert('Error', 'Failed to refresh images');
    } finally {
      setRefreshingGifs(false);
    }
  };

  // Update the manual week override (stored on the program)
  const updateWeekOverride = async (week: number) => {
    if (!workout) return;
    try {
      await api.patch(`/workout/${workout.id}/week-override`, { current_week_override: week });
      setWorkout({ ...workout, current_week_override: week });
    } catch {
      // silent — optimistic update won't reflect without success, that's fine
    }
    setShowWeekModal(false);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
      </SafeAreaView>
    );
  }

  if (!workout) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>
        <Text style={styles.errorText}>Workout not found</Text>
      </SafeAreaView>
    );
  }

  // Renders ONLY the tappable header row of each exercise card (used inside Pressable)
  const renderExerciseHeader = (exercise: Exercise, exIdx: number, isSelected: boolean, isSwapMode: boolean) => (
    <View style={styles.exerciseHeader}>
      {/* Position number / swap indicator */}
      {isSelected ? (
        <View style={[styles.exerciseNumber, styles.exerciseNumberSelected]}>
          <Ionicons name="swap-vertical" size={16} color={colors.background} />
        </View>
      ) : isSwapMode ? (
        <View style={[styles.exerciseNumber, styles.exerciseNumberSwapTarget]}>
          <Text style={[styles.exerciseNumberText, { color: colors.primary }]}>{exIdx + 1}</Text>
        </View>
      ) : exercise.gif_url ? (
        <Image
          source={{ uri: getFullGifUrl(exercise.gif_url) || '' }}
          style={styles.exerciseThumbnail}
          resizeMode="cover"
        />
      ) : (
        <View style={styles.exerciseNumber}>
          <Text style={styles.exerciseNumberText}>{exIdx + 1}</Text>
        </View>
      )}

      <View style={styles.exerciseInfo}>
        <Text style={[styles.exerciseName, isSelected && styles.exerciseNameSelected]}>
          {exercise.name}
        </Text>
        <Text style={styles.exerciseMeta}>
          {exercise.sets} sets × {exercise.reps} reps • {exercise.rest_seconds}s rest
        </Text>
        {isSelected && (
          <Text style={styles.swapHint}>Tap another exercise to swap</Text>
        )}
        {isSwapMode && !isSelected && (
          <Text style={styles.swapTargetHint}>Tap to swap here</Text>
        )}
      </View>

      {isSelected ? (
        <View style={styles.selectedBadge}>
          <Ionicons name="checkmark" size={14} color={colors.background} />
        </View>
      ) : (
        <Ionicons
          name={expandedExercise === `${expandedDay}-${exIdx}` ? 'chevron-up' : 'chevron-down'}
          size={20}
          color={isSwapMode ? colors.primary : colors.textSecondary}
        />
      )}
    </View>
  );

  // Renders the expanded detail panel — kept OUTSIDE the Pressable so TextInput
  // touches never bubble up to the exercise card's tap/long-press handler.
  const renderExerciseDetailPanel = (exercise: Exercise, exIdx: number) => (
    <View style={styles.exerciseDetails}>
      {exercise.gif_url && (
        <View style={styles.gifContainer}>
          <Image
            source={{ uri: getFullGifUrl(exercise.gif_url) || '' }}
            style={styles.exerciseGif}
            resizeMode="contain"
          />
        </View>
      )}
      <View style={styles.detailSection}>
        <Text style={styles.detailLabel}>Instructions</Text>
        <Text style={styles.detailText}>{exercise.instructions}</Text>
      </View>
      <View style={styles.detailRow}>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Equipment</Text>
          <Text style={styles.detailValue}>{exercise.equipment || 'varies'}</Text>
        </View>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Muscles</Text>
          <Text style={styles.detailValue}>
            {Array.isArray(exercise.muscle_groups)
              ? exercise.muscle_groups.join(', ')
              : exercise.muscle_groups || 'various'}
          </Text>
        </View>
      </View>
      {exercise.substitution_hint && (
        <View style={styles.substitutionRow}>
          <Ionicons name="swap-horizontal" size={14} color={colors.textSecondary} />
          <Text style={styles.substitutionText}>
            <Text style={styles.substitutionLabel}>Alternatives: </Text>
            {exercise.substitution_hint}
          </Text>
        </View>
      )}
      <View style={styles.trackingSection}>
        <View style={styles.trackingHeader}>
          <Text style={styles.trackingTitle}>Log Your Sets</Text>
          <TouchableOpacity style={styles.addSetBtn} onPress={() => addSet(expandedDay, exIdx)}>
            <Ionicons name="add" size={18} color={colors.primary} />
            <Text style={styles.addSetText}>Add Set</Text>
          </TouchableOpacity>
        </View>
        {Array.from({ length: exercise.sets }, (_, setIdx) => {
          const key = `${expandedDay}-${exIdx}-${setIdx}`;
          const perf = performance[key] || { weight: '', reps: '', completed: false };
          const hint = getLastTimeHint(expandedDay, exIdx, setIdx);
          return (
            <View key={setIdx}>
              <View style={styles.setRow}>
                <TouchableOpacity
                  style={[styles.setCheckbox, perf.completed && styles.setCheckboxChecked]}
                  onPress={() => updatePerformance(key, { ...perf, completed: !perf.completed })}
                >
                  {perf.completed && <Ionicons name="checkmark" size={16} color={colors.background} />}
                </TouchableOpacity>
                <Text style={styles.setLabel}>Set {setIdx + 1}</Text>
                <TextInput
                  style={styles.setInput}
                  placeholder={localUnit}
                  placeholderTextColor={colors.textMuted}
                  keyboardType="decimal-pad"
                  value={perf.weight}
                  onChangeText={(text) => updatePerformance(key, { ...perf, weight: text })}
                />
                <Text style={styles.setX}>×</Text>
                <TextInput
                  style={styles.setInput}
                  placeholder="reps"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="number-pad"
                  value={perf.reps}
                  onChangeText={(text) => updatePerformance(key, { ...perf, reps: text })}
                />
                <TouchableOpacity style={styles.removeSetBtn} onPress={() => removeSet(expandedDay, exIdx)}>
                  <Ionicons name="close-circle" size={22} color={colors.error} />
                </TouchableOpacity>
              </View>
              {hint && (
                <Text style={styles.lastTimeHint}>Last time: {hint}</Text>
              )}
            </View>
          );
        })}
      </View>
      <View style={styles.exerciseActions}>
        <TouchableOpacity style={styles.actionBtn} onPress={() => openReplaceExerciseModal(expandedDay, exIdx)}>
          <Ionicons name="swap-horizontal" size={18} color={colors.primary} />
          <Text style={styles.actionBtnText}>Replace</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.actionBtnDanger]} onPress={() => deleteExercise(expandedDay, exIdx)}>
          <Ionicons name="trash-outline" size={18} color={colors.error} />
          <Text style={[styles.actionBtnText, styles.actionBtnTextDanger]}>Delete</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Workout Program</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Program Info */}
        <View style={styles.infoCard}>
          <TouchableOpacity 
            style={styles.nameRow} 
            onPress={() => {
              setNewName(workout.name);
              setShowRenameModal(true);
            }}
          >
            <Text style={styles.programName}>{workout.name}</Text>
            <Ionicons name="pencil" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
          <Text style={styles.programGoal}>
            {workout.goal.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            {workout.training_style ? ` · ${workout.training_style.charAt(0).toUpperCase() + workout.training_style.slice(1)}` : ''}
          </Text>
          
          <View style={styles.infoRow}>
            <View style={styles.infoItem}>
              <Ionicons name="calendar" size={20} color={colors.primary} />
              <Text style={styles.infoText}>{workout.days_per_week} days/week</Text>
            </View>
            <View style={styles.infoItem}>
              <Ionicons name="git-branch" size={20} color={colors.primary} />
              <Text style={styles.infoText}>{workout.split_name || 'Custom Split'}</Text>
            </View>
          </View>

          {workout.focus_areas && (
            <View style={styles.tagContainer}>
              {(workout.focus_areas || []).map((area, idx) => (
                <View key={idx} style={styles.tag}>
                  <Text style={styles.tagText}>{area}</Text>
                </View>
              ))}
              {(workout.secondary_focus_areas || []).map((area, idx) => (
                <View key={`sec-${idx}`} style={[styles.tag, styles.tagSecondary]}>
                  <Text style={styles.tagText}>{area}</Text>
                </View>
              ))}
            </View>
          )}
          
          {/* Refresh GIFs Button */}
          <TouchableOpacity
            style={styles.refreshGifsBtn}
            onPress={refreshGifs}
            disabled={refreshingGifs}
          >
            {refreshingGifs ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Ionicons name="refresh" size={16} color={colors.primary} />
            )}
            <Text style={styles.refreshGifsBtnText}>
              {refreshingGifs ? 'Refreshing...' : 'Refresh Exercise Images'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* ── 4-Week Progression Banner ─────────────────────────────────────── */}
        {workout.weekly_progression && workout.weekly_progression.length > 0 && (() => {
          const weekData = workout.weekly_progression![currentWeek - 1];
          return (
            <TouchableOpacity
              style={styles.weekBanner}
              onPress={() => setShowWeekModal(true)}
              activeOpacity={0.8}
            >
              <View style={styles.weekBannerTop}>
                <View style={styles.weekBannerBadge}>
                  <Ionicons name="calendar-outline" size={13} color={colors.primary} />
                  <Text style={styles.weekBannerBadgeText}>Week {currentWeek} of 12</Text>
                </View>
                <Text style={styles.weekBannerLabel}>{weekData?.label}</Text>
                <Ionicons name="create-outline" size={15} color={colors.textMuted} style={{ marginLeft: 'auto' }} />
              </View>
              <Text style={styles.weekBannerInstruction}>
                {weekData?.instruction}
              </Text>
              {currentWeek === 12 && (
                <View style={styles.weekCompleteRow}>
                  <Ionicons name="trophy-outline" size={13} color={colors.warning} />
                  <Text style={styles.weekCompleteText}>
                    {"You've completed your 12-week program — time for a fresh one to keep progressing!"}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })()}

        {/* Premium Coaching Panel */}
        {(workout.split_rationale || workout.progression_method || workout.weekly_structure) && (
          <View style={styles.coachingPanel}>
            <View style={styles.coachingPanelHeader}>
              <Ionicons name="sparkles" size={18} color={colors.primary} />
              <Text style={styles.coachingPanelTitle}>Elite Coaching Breakdown</Text>
            </View>

            {workout.split_rationale && (
              <View style={styles.coachingRow}>
                <View style={styles.coachingIcon}>
                  <Ionicons name="information-circle" size={16} color={colors.primary} />
                </View>
                <View style={styles.coachingContent}>
                  <Text style={styles.coachingLabel}>Why this split</Text>
                  <Text style={styles.coachingValue}>{workout.split_rationale}</Text>
                </View>
              </View>
            )}

            {/* Effort guideline removed per product philosophy — keep it simple */}

            {workout.progression_method && (
              <View style={styles.coachingRow}>
                <View style={styles.coachingIcon}>
                  <Ionicons name="trending-up" size={16} color={colors.primary} />
                </View>
                <View style={styles.coachingContent}>
                  <Text style={styles.coachingLabel}>Progression Method</Text>
                  <Text style={styles.coachingValue}>{workout.progression_method}</Text>
                </View>
              </View>
            )}

            {workout.deload_timing && (
              <View style={styles.coachingRow}>
                <View style={styles.coachingIcon}>
                  <Ionicons name="refresh-circle" size={16} color={colors.primary} />
                </View>
                <View style={styles.coachingContent}>
                  <Text style={styles.coachingLabel}>Deload Protocol</Text>
                  <Text style={styles.coachingValue}>{workout.deload_timing}</Text>
                </View>
              </View>
            )}

            {workout.weekly_structure && workout.weekly_structure.length > 0 && (
              <View style={styles.weeklyStructure}>
                <Text style={styles.coachingLabel}>Weekly Blueprint</Text>
                {workout.weekly_structure.map((day, idx) => {
                  const isRest = day.endsWith(': Rest');
                  const dayName = day.split(':')[0];
                  if (isRest) {
                    return (
                      <View key={idx} style={styles.weeklyRestRow}>
                        <Ionicons name="moon-outline" size={14} color={colors.textMuted} />
                        <View style={{ flex: 1 }}>
                          <Text style={styles.weeklyRestDayName}>{dayName}</Text>
                          <Text style={styles.weeklyRestSubText}>Rest & Recovery — Light walk, stretching, or full rest.</Text>
                        </View>
                      </View>
                    );
                  }
                  return (
                    <View key={idx} style={styles.weeklyDayRow}>
                      <View style={styles.weeklyDayDot} />
                      <Text style={styles.weeklyDayText}>{day}</Text>
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        )}

        {/* Day Tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dayTabs}>
          {workout.workout_days.map((day, idx) => (
            <TouchableOpacity
              key={idx}
              style={[styles.dayTab, expandedDay === idx && styles.dayTabActive]}
              onPress={() => setExpandedDay(idx)}
            >
              <Text style={[styles.dayTabText, expandedDay === idx && styles.dayTabTextActive]}>
                Day {idx + 1}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Current Day */}
        {workout.workout_days[expandedDay] && (
          <View style={styles.dayContent}>
            <View style={styles.dayHeader}>
              <Text style={styles.dayTitle} numberOfLines={1}>{workout.workout_days[expandedDay].day}</Text>
              <View style={styles.dayHeaderRight}>
                {/* Inline unit pill toggle */}
                <View style={styles.unitPillContainer}>
                  <TouchableOpacity
                    style={[styles.unitPillBtn, localUnit === 'kg' && styles.unitPillBtnActive]}
                    onPress={() => localUnit !== 'kg' && toggleLocalUnit()}
                  >
                    <Text style={[styles.unitPillText, localUnit === 'kg' && styles.unitPillTextActive]}>kg</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.unitPillBtn, localUnit === 'lbs' && styles.unitPillBtnActive]}
                    onPress={() => localUnit !== 'lbs' && toggleLocalUnit()}
                  >
                    <Text style={[styles.unitPillText, localUnit === 'lbs' && styles.unitPillTextActive]}>lbs</Text>
                  </TouchableOpacity>
                </View>
                <View style={styles.dayMeta}>
                  <Ionicons name="time" size={16} color={colors.textSecondary} />
                  <Text style={styles.dayMetaText}>
                    ~{workout.workout_days[expandedDay].duration_minutes} min
                  </Text>
                </View>
              </View>
            </View>

            {workout.workout_days[expandedDay].notes && (
              <View style={styles.notesCard}>
                <Ionicons name="information-circle" size={18} color={colors.primary} />
                <Text style={styles.notesText}>{workout.workout_days[expandedDay].notes}</Text>
              </View>
            )}

            {/* Exercises — long press to select, tap to swap */}
            {selectedExIdx !== null && (
              <View style={styles.swapBanner}>
                <Ionicons name="swap-vertical" size={16} color={colors.background} />
                <Text style={styles.swapBannerText}>
                  Tap any exercise to swap • Tap selected again to cancel
                </Text>
              </View>
            )}
            {workout.workout_days[expandedDay].exercises.map((exercise, exIdx) => {
              const isSelected = selectedExIdx === exIdx;
              const isSwapMode = selectedExIdx !== null;

              return (
                <View
                  key={`${exercise.name}-${exIdx}`}
                  style={[
                    styles.exerciseCard,
                    isSelected && styles.exerciseCardSelected,
                    isSwapMode && !isSelected && styles.exerciseCardSwapTarget,
                  ]}
                >
                  {/* ── Tappable header — Pressable only wraps this row ── */}
                  <Pressable
                    onPress={() => handleExerciseTap(exIdx)}
                    onLongPress={() => handleExerciseLongPress(exIdx)}
                    delayLongPress={700}
                    style={({ pressed }) => [pressed && !isSelected && styles.exerciseCardPressed]}
                  >
                    {isSelected ? (
                      <Animated.View style={{ opacity: swapPulse.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }) }}>
                        {renderExerciseHeader(exercise, exIdx, isSelected, isSwapMode)}
                      </Animated.View>
                    ) : (
                      renderExerciseHeader(exercise, exIdx, isSelected, isSwapMode)
                    )}
                  </Pressable>

                  {/* ── Detail panel is OUTSIDE the Pressable so TextInput taps
                        never bubble up to the card's tap/long-press handler ── */}
                  {!isSwapMode && expandedExercise === `${expandedDay}-${exIdx}` && (
                    renderExerciseDetailPanel(exercise, exIdx)
                  )}
                </View>
              );
            })}

            {/* Add Exercise Button - at the end of exercise list */}
            <TouchableOpacity
              style={styles.addExerciseBtn}
              onPress={() => openAddExerciseModal(expandedDay)}
            >
              <Ionicons name="add-circle-outline" size={22} color={colors.primary} />
              <Text style={styles.addExerciseBtnText}>Add Exercise</Text>
            </TouchableOpacity>

            {/* Finish Workout Button */}
            <TouchableOpacity
              style={[styles.finishWorkoutBtn, finishing && styles.finishWorkoutBtnDisabled]}
              onPress={handleFinishWorkout}
              disabled={finishing}
            >
              {finishing ? (
                <ActivityIndicator size="small" color="#000" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={22} color="#000" />
                  <Text style={styles.finishWorkoutBtnText}>Finish Workout</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* Photo picker modal — Android only (iOS uses ActionSheetIOS) */}
      <Modal
        visible={showPhotoPickerModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowPhotoPickerModal(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowPhotoPickerModal(false)}
        >
          <View style={[styles.modalContent, styles.photoPickerModal]}>
            <TouchableOpacity
              style={styles.photoPickerOption}
              onPress={() => { setShowPhotoPickerModal(false); handleTakePhoto(); }}
            >
              <Ionicons name="camera-outline" size={22} color={colors.text} />
              <Text style={styles.photoPickerOptionText}>Take Photo</Text>
            </TouchableOpacity>
            <View style={styles.photoPickerDivider} />
            <TouchableOpacity
              style={styles.photoPickerOption}
              onPress={() => { setShowPhotoPickerModal(false); handleChooseFromLibrary(); }}
            >
              <Ionicons name="images-outline" size={22} color={colors.text} />
              <Text style={styles.photoPickerOptionText}>Choose from Library</Text>
            </TouchableOpacity>
            <View style={styles.photoPickerDivider} />
            <TouchableOpacity
              style={styles.photoPickerOption}
              onPress={() => setShowPhotoPickerModal(false)}
            >
              <Text style={[styles.photoPickerOptionText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Workout Complete Modal */}
      <Modal
        visible={showCompleteModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowCompleteModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, styles.completeModalContent]}>
            <Text style={styles.completeEmoji}>💪</Text>
            <Text style={styles.completeTitle}>Workout Complete!</Text>

            {completedSessionData && (
              <>
                {/* Streak */}
                {completedSessionData.current_streak > 0 && (
                  <View style={styles.completeStreakBadge}>
                    <Text style={styles.completeStreakText}>
                      🔥 {completedSessionData.current_streak} workout streak!
                    </Text>
                  </View>
                )}

                {/* Volume & Duration */}
                {completedSessionData.volume > 0 && (
                  <View style={styles.completeStatRow}>
                    <Ionicons name="barbell" size={18} color={colors.primary} />
                    <Text style={styles.completeStat}>
                      {localUnit === 'lbs'
                        ? `${Math.round(kgToDisplay(completedSessionData.volume)).toLocaleString()} lbs total volume`
                        : `${completedSessionData.volume.toLocaleString()} kg total volume`}
                    </Text>
                  </View>
                )}
                {completedSessionData.duration && (
                  <View style={styles.completeStatRow}>
                    <Ionicons name="time" size={18} color={colors.primary} />
                    <Text style={styles.completeStat}>
                      {completedSessionData.duration} {completedSessionData.duration === 1 ? 'minute' : 'minutes'}
                    </Text>
                  </View>
                )}

                {/* Personal Records — inline, no modal */}
                {completedSessionData.personal_records.length > 0 && (
                  <View style={styles.prSection}>
                    {completedSessionData.personal_records.map((pr, i) => (
                      <View key={i} style={styles.prRow}>
                        <Text style={styles.prTrophy}>🏆</Text>
                        <View style={styles.prTextBlock}>
                          <Text style={styles.prExercise}>{pr.exercise_name}</Text>
                          <Text style={styles.prDetail}>
                            {pr.type === 'weight'
                              ? `New PR! ${localUnit === 'lbs' ? kgToDisplay(pr.new_value) : pr.new_value}${localUnit}${pr.previous_value ? ` (was ${localUnit === 'lbs' ? kgToDisplay(pr.previous_value) : pr.previous_value}${localUnit})` : ' — first lift!'}`
                              : `New reps PR! ${pr.new_value} reps (was ${pr.previous_value})`}
                          </Text>
                        </View>
                      </View>
                    ))}
                  </View>
                )}

                {/* Optional workout photo */}
                {sessionPhotoUri ? (
                  <Image source={{ uri: sessionPhotoUri }} style={styles.sessionPhotoThumb} />
                ) : (
                  <TouchableOpacity style={styles.addPhotoBtn} onPress={handleAddPhoto} disabled={photoUploading}>
                    {photoUploading
                      ? <ActivityIndicator size="small" color={colors.textSecondary} />
                      : <>
                          <Ionicons name="camera-outline" size={18} color={colors.textSecondary} />
                          <Text style={styles.addPhotoBtnText}>Add photo (optional)</Text>
                        </>
                    }
                  </TouchableOpacity>
                )}
              </>
            )}

            <TouchableOpacity
              style={styles.completeDoneBtn}
              onPress={() => setShowCompleteModal(false)}
            >
              <Text style={styles.completeDoneBtnText}>Keep Going 🔥</Text>
            </TouchableOpacity>

            {/* Confetti burst — inside card with overflow visible */}
            <ConfettiBurst active={!!(completedSessionData?.personal_records?.length)} />
          </View>
        </View>
      </Modal>

      {/* Rename Modal */}
      <Modal
        visible={showRenameModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowRenameModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Rename Workout</Text>
            <TextInput
              style={styles.renameInput}
              value={newName}
              onChangeText={setNewName}
              placeholder="Enter new name"
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity 
                style={styles.modalCancelBtn}
                onPress={() => setShowRenameModal(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.modalSaveBtn, renaming && styles.modalBtnDisabled]}
                onPress={handleRename}
                disabled={renaming}
              >
                {renaming ? (
                  <ActivityIndicator size="small" color={colors.background} />
                ) : (
                  <Text style={styles.modalSaveText}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Week Picker Modal */}
      <Modal
        visible={showWeekModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowWeekModal(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowWeekModal(false)}
        >
          <View style={[styles.modalContent, { maxWidth: 320 }]}>
            <Text style={styles.modalTitle}>Adjust Current Week</Text>
            <Text style={[styles.coachingValue, { textAlign: 'center', marginBottom: 20, fontSize: 13 }]}>
              If you fell behind or took a rest week, set your actual week here.
            </Text>
            {workout?.weekly_progression?.map((w) => (
              <TouchableOpacity
                key={w.week}
                style={[styles.weekPickerOption, currentWeek === w.week && styles.weekPickerOptionActive]}
                onPress={() => updateWeekOverride(w.week)}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[styles.weekPickerOptionWeek, currentWeek === w.week && styles.weekPickerOptionWeekActive]}>
                    Week {w.week}
                  </Text>
                  <Text style={styles.weekPickerOptionLabel}>{w.label}</Text>
                </View>
                {currentWeek === w.week && (
                  <Ionicons name="checkmark-circle" size={20} color={colors.primary} />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Replace Exercise Modal */}
      <Modal
        visible={showReplaceModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowReplaceModal(false)}
      >
        <View style={styles.replaceModalContainer}>
          <View style={styles.replaceModalContent}>
            {/* Header with drag indicator */}
            <View style={styles.modalDragIndicator} />
            <View style={styles.replaceModalHeader}>
              <Text style={styles.replaceModalTitle}>{isAddMode ? 'Add Exercise' : 'Replace Exercise'}</Text>
              <TouchableOpacity 
                style={styles.modalCloseBtn}
                onPress={() => {
                  setShowReplaceModal(false);
                  setReplaceTarget(null);
                  setIsAddMode(false);
                  setAddToDayIdx(null);
                  setSearchQuery('');
                  setSearchResults([]);
                  setSelectedMuscle(null);
                }}
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>

            {/* Search Bar */}
            <View style={styles.searchBarContainer}>
              <Ionicons name="search" size={20} color={colors.textMuted} style={styles.searchIcon} />
              <TextInput
                style={styles.searchBar}
                placeholder="Search exercises..."
                placeholderTextColor={colors.textMuted}
                value={searchQuery}
                onChangeText={(text) => {
                  setSearchQuery(text);
                  debouncedSearch(text, selectedMuscle || undefined);
                }}
                autoCapitalize="none"
                autoCorrect={false}
              />
              {searchQuery.length > 0 && (
                <TouchableOpacity 
                  style={styles.clearSearchBtn}
                  onPress={() => {
                    setSearchQuery('');
                    searchExercises('', selectedMuscle || undefined);
                  }}
                >
                  <Ionicons name="close-circle" size={20} color={colors.textMuted} />
                </TouchableOpacity>
              )}
            </View>

            {/* Muscle Group Filter - Visual icons with labels */}
            <ScrollView 
              horizontal 
              showsHorizontalScrollIndicator={false} 
              style={styles.muscleFilterScroll}
              contentContainerStyle={styles.muscleFilterContent}
            >
              <TouchableOpacity
                style={[styles.muscleFilterChip, !selectedMuscle && styles.muscleFilterChipActive]}
                onPress={() => {
                  setSelectedMuscle(null);
                  searchExercises(searchQuery, undefined);
                }}
              >
                <View style={[styles.muscleIconContainer, !selectedMuscle && styles.muscleIconContainerActive]}>
                  <Ionicons name="apps" size={18} color={!selectedMuscle ? colors.background : colors.primary} />
                </View>
                <Text style={[styles.muscleFilterText, !selectedMuscle && styles.muscleFilterTextActive]}>All</Text>
              </TouchableOpacity>
              {muscleGroups.map((muscle) => (
                <TouchableOpacity
                  key={muscle.id}
                  style={[styles.muscleFilterChip, selectedMuscle === muscle.id && styles.muscleFilterChipActive]}
                  onPress={() => {
                    setSelectedMuscle(muscle.id);
                    searchExercises(searchQuery, muscle.id);
                  }}
                >
                  <View style={[styles.muscleIconContainer, selectedMuscle === muscle.id && styles.muscleIconContainerActive]}>
                    <Text style={styles.muscleEmoji}>{muscle.emoji}</Text>
                  </View>
                  <Text style={[styles.muscleFilterText, selectedMuscle === muscle.id && styles.muscleFilterTextActive]}>
                    {muscle.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Recommended Swaps (from current exercise substitution_hint) */}
            {!isAddMode && replaceTarget && (() => {
              const curEx = workout?.workout_days[replaceTarget.dayIdx]?.exercises[replaceTarget.exIdx];
              const hints = (curEx?.substitution_hint || '')
                .split(',').map((s: string) => s.trim()).filter(Boolean);
              if (!hints.length) return null;
              return (
                <View style={styles.recommendedSwaps}>
                  <Text style={styles.recommendedSwapsTitle}>Recommended Swaps</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                    {hints.map((hint: string, i: number) => (
                      <TouchableOpacity
                        key={i}
                        style={styles.recommendedSwapChip}
                        onPress={() => {
                          setSearchQuery(hint);
                          searchExercises(hint, selectedMuscle || undefined);
                        }}
                      >
                        <Ionicons name="swap-horizontal" size={12} color={colors.primary} />
                        <Text style={styles.recommendedSwapText}>{hint}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>
              );
            })()}

            {/* Search Results */}
            <ScrollView style={styles.searchResults} showsVerticalScrollIndicator={false}>
              {searching ? (
                <View style={styles.loadingContainer}>
                  <ActivityIndicator size="large" color={colors.primary} />
                  <Text style={styles.loadingText}>Searching exercises...</Text>
                </View>
              ) : searchResults.length === 0 ? (
                <View style={styles.noResults}>
                  <Ionicons name="barbell-outline" size={48} color={colors.textMuted} />
                  <Text style={styles.noResultsText}>
                    {selectedMuscle
                      ? `No exercises found for "${muscleGroups.find(m => m.id === selectedMuscle)?.label ?? selectedMuscle}"`
                      : 'Select a muscle group to browse the library'}
                  </Text>
                </View>
              ) : (
                <>
                  <Text style={styles.resultsCount}>
                    {searchResults.length} of {exerciseTotalCount} exercises
                  </Text>
                  {searchResults.map((ex, idx) => (
                    <TouchableOpacity
                      key={idx}
                      style={styles.exerciseResult}
                      onPress={() => handleExerciseSelect(ex)}
                    >
                      {ex.gifUrl ? (
                        <Image source={{ uri: getFullGifUrl(ex.gifUrl) || '' }} style={styles.exerciseResultGif} />
                      ) : (
                        <View style={styles.exerciseResultPlaceholder}>
                          <Ionicons name="image-outline" size={24} color={colors.textMuted} />
                        </View>
                      )}
                      <View style={styles.exerciseResultInfo}>
                        <Text style={styles.exerciseResultName} numberOfLines={2}>{ex.name}</Text>
                        <Text style={styles.exerciseResultMuscle}>
                          {ex.target} • {ex.equipment}
                        </Text>
                      </View>
                      <View style={styles.selectBadge}>
                        <Text style={styles.selectBadgeText}>{isAddMode ? 'Add' : 'Select'}</Text>
                      </View>
                    </TouchableOpacity>
                  ))}

                  {/* Load More button */}
                  {searchResults.length < exerciseTotalCount && (
                    <TouchableOpacity
                      style={styles.loadMoreBtn}
                      onPress={() => searchExercises(searchQuery, selectedMuscle || undefined, true, exerciseOffset)}
                      disabled={loadingMore}
                    >
                      {loadingMore ? (
                        <ActivityIndicator size="small" color={colors.primary} />
                      ) : (
                        <>
                          <Ionicons name="chevron-down" size={16} color={colors.primary} />
                          <Text style={styles.loadMoreText}>
                            Load more ({exerciseTotalCount - searchResults.length} remaining)
                          </Text>
                        </>
                      )}
                    </TouchableOpacity>
                  )}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loader: {
    flex: 1,
    justifyContent: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  errorText: {
    color: colors.text,
    textAlign: 'center',
    marginTop: 40,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  programName: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  programGoal: {
    fontSize: 16,
    color: colors.primary,
    marginTop: 4,
  },
  infoRow: {
    flexDirection: 'row',
    gap: 24,
    marginTop: 16,
  },
  infoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  infoText: {
    fontSize: 14,
    color: colors.text,
  },
  tagContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 16,
  },
  tag: {
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primary + '40',
  },
  tagSecondary: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tagText: {
    fontSize: 12,
    color: colors.primary,
  },
  // Coaching Panel
  coachingPanel: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  coachingPanelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  coachingPanelTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  coachingRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 14,
  },
  coachingIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary + '15',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  coachingContent: {
    flex: 1,
  },
  coachingLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 3,
  },
  coachingValue: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  weeklyStructure: {
    marginTop: 6,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  weeklyDayRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  weeklyDayDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
    flexShrink: 0,
  },
  weeklyDayText: {
    fontSize: 13,
    color: colors.textSecondary,
    flex: 1,
  },
  // Rest day row in weekly blueprint
  weeklyRestRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    backgroundColor: colors.surfaceLight,
    borderRadius: 8,
    opacity: 0.7,
  },
  weeklyRestDayName: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  weeklyRestSubText: {
    fontSize: 11,
    color: colors.textMuted,
    fontStyle: 'italic',
    lineHeight: 16,
    marginTop: 1,
  },
  // 4-Week Progression Banner
  weekBanner: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  weekBannerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  weekBannerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  weekBannerBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.primary,
  },
  weekBannerLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  weekBannerInstruction: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  weekCompleteRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  weekCompleteText: {
    fontSize: 12,
    color: colors.warning,
    flex: 1,
    lineHeight: 17,
  },
  // Week picker modal options
  weekPickerOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: colors.background,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  weekPickerOptionActive: {
    backgroundColor: colors.primary + '15',
    borderColor: colors.primary + '60',
  },
  weekPickerOptionWeek: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
  },
  weekPickerOptionWeekActive: {
    color: colors.primary,
  },
  weekPickerOptionLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  // Substitution hint
  substitutionRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  substitutionText: {
    fontSize: 12,
    color: colors.textSecondary,
    flex: 1,
    lineHeight: 17,
  },
  substitutionLabel: {
    fontWeight: '600',
    color: colors.textSecondary,
  },
  refreshGifsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: colors.primary + '15',
    borderRadius: 20,
    alignSelf: 'flex-start',
  },
  refreshGifsBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.primary,
  },
  dayTabs: {
    marginBottom: 16,
  },
  dayTab: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.surface,
    marginRight: 10,
  },
  dayTabActive: {
    backgroundColor: colors.primary,
  },
  dayTabText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  dayTabTextActive: {
    color: colors.background,
  },
  dayContent: {
    gap: 12,
  },
  dayHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
    gap: 8,
  },
  dayHeaderRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  unitPillContainer: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  unitPillBtn: {
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  unitPillBtnActive: {
    backgroundColor: colors.primary,
    borderRadius: 20,
  },
  unitPillText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textMuted,
    letterSpacing: 0.3,
  },
  unitPillTextActive: {
    color: '#000',
  },
  dayTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  dayMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dayMetaText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  notesCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.primary + '15',
    padding: 12,
    borderRadius: 10,
    gap: 10,
  },
  notesText: {
    flex: 1,
    fontSize: 13,
    color: colors.text,
    lineHeight: 18,
  },
  exerciseCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  exerciseCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '18',
  },
  exerciseCardSwapTarget: {
    borderColor: colors.primary + '60',
    backgroundColor: colors.primary + '08',
  },
  exerciseCardPressed: {
    opacity: 0.85,
  },
  // Swap banner
  swapBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 4,
  },
  swapBannerText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.background,
    flex: 1,
  },
  swapHint: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '600',
    marginTop: 2,
  },
  swapTargetHint: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '500',
    marginTop: 2,
  },
  exerciseNameSelected: {
    color: colors.primary,
  },
  selectedBadge: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  exerciseNumberSelected: {
    backgroundColor: colors.primary,
  },
  exerciseNumberSwapTarget: {
    borderWidth: 2,
    borderColor: colors.primary,
    backgroundColor: 'transparent',
  },
  exerciseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  exerciseNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  exerciseThumbnail: {
    width: 56,
    height: 56,
    borderRadius: 10,
    backgroundColor: colors.surfaceLight,
  },
  exerciseNumberText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.primary,
  },
  exerciseInfo: {
    flex: 1,
    marginLeft: 12,
  },
  exerciseName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  exerciseMeta: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  exerciseDetails: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  gifContainer: {
    alignItems: 'center',
    marginBottom: 16,
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    overflow: 'hidden',
  },
  exerciseGif: {
    width: '100%',
    height: 200,
  },
  detailSection: {
    marginBottom: 16,
  },
  detailLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  detailText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  detailRow: {
    flexDirection: 'row',
    gap: 20,
  },
  detailItem: {
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    color: colors.text,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 340,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
    marginBottom: 20,
  },
  renameInput: {
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  modalCancelBtn: {
    flex: 1,
    padding: 14,
    borderRadius: 10,
    backgroundColor: colors.surfaceLight,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  modalSaveBtn: {
    flex: 1,
    padding: 14,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: 'center',
  },
  modalSaveText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  modalBtnDisabled: {
    opacity: 0.7,
  },
  trackingSection: {
    marginTop: 16,
    padding: 16,
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
  },
  trackingTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
  },
  setRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 8,
  },
  setCheckbox: {
    width: 28,
    height: 28,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.textMuted,
    justifyContent: 'center',
    alignItems: 'center',
  },
  setCheckboxChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  setLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    width: 50,
  },
  setInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: colors.text,
    textAlign: 'center',
  },
  setX: {
    fontSize: 16,
    color: colors.textMuted,
  },
  trackingHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  addSetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.primary + '20',
  },
  addSetText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.primary,
  },
  exerciseActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.surfaceLight,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.primary + '15',
  },
  actionBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
  },
  actionBtnDanger: {
    backgroundColor: colors.error + '15',
  },
  actionBtnTextDanger: {
    color: colors.error,
  },
  addExerciseBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: colors.primary + '40',
    borderStyle: 'dashed',
  },
  addExerciseBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.primary,
  },
  replaceModalContainer: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  replaceModalContent: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    height: '90%',
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  modalDragIndicator: {
    width: 40,
    height: 4,
    backgroundColor: colors.textMuted,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 12,
    marginBottom: 8,
  },
  replaceModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingTop: 4,
  },
  modalCloseBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  replaceModalTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  // Search bar styles
  searchBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchBar: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.text,
  },
  clearSearchBtn: {
    padding: 4,
  },
  // Muscle filter styles - compact version
  muscleFilterScroll: {
    marginBottom: 8,
    maxHeight: 44,
  },
  muscleFilterContent: {
    paddingRight: 16,
    gap: 6,
  },
  muscleFilterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 5,
  },
  muscleFilterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  muscleFilterText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  muscleFilterTextActive: {
    color: '#000',
    fontWeight: '700',
  },
  muscleIconContainer: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  muscleIconContainerActive: {
    backgroundColor: colors.background,
  },
  muscleEmoji: {
    fontSize: 11,
  },
  manualEntrySection: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
  },
  manualEntryLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  manualEntryRow: {
    flexDirection: 'row',
    gap: 10,
  },
  manualEntryInput: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 15,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  manualAddBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingHorizontal: 16,
    gap: 4,
  },
  manualAddBtnDisabled: {
    backgroundColor: colors.surfaceLight,
  },
  manualAddBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.background,
  },
  manualAddBtnTextDisabled: {
    color: colors.textMuted,
  },
  modalDivider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 10,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    fontSize: 11,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  muscleGridLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  muscleGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  muscleGridItem: {
    width: '19%',
    aspectRatio: 1,
    backgroundColor: colors.surface,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 2,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  muscleGridItemActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '15',
  },
  muscleGridText: {
    fontSize: 9,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  muscleGridTextActive: {
    color: colors.primary,
  },
  loadingContainer: {
    alignItems: 'center',
    paddingTop: 30,
    gap: 10,
  },
  loadingText: {
    fontSize: 13,
    color: colors.textMuted,
  },
  resultsCount: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 8,
    fontWeight: '500',
  },
  // Recommended swaps section
  recommendedSwaps: {
    marginHorizontal: 16,
    marginBottom: 8,
  },
  recommendedSwapsTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  recommendedSwapChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: colors.primary + '15',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.primary + '40',
    marginRight: 6,
  },
  recommendedSwapText: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: '500',
  },
  // Load more button
  loadMoreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 14,
    marginTop: 6,
    marginBottom: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  loadMoreText: {
    fontSize: 13,
    color: colors.primary,
    fontWeight: '500',
  },
  searchResults: {
    flex: 1,
  },
  noResults: {
    alignItems: 'center',
    paddingTop: 30,
    gap: 10,
  },
  noResultsText: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    paddingHorizontal: 16,
  },
  exerciseResult: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 8,
    backgroundColor: colors.surface,
    borderRadius: 10,
    marginBottom: 6,
    gap: 10,
  },
  exerciseResultGif: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: colors.surfaceLight,
  },
  exerciseResultPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  exerciseResultInfo: {
    flex: 1,
  },
  exerciseResultName: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
    textTransform: 'capitalize',
  },
  exerciseResultMuscle: {
    fontSize: 11,
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  selectBadge: {
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  selectBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
  },
  removeSetBtn: {
    padding: 4,
    marginLeft: 4,
  },
  // Session history styles
  lastTimeHint: {
    fontSize: 11,
    color: colors.textMuted,
    fontStyle: 'italic',
    marginLeft: 44,
    marginBottom: 6,
    marginTop: -2,
  },
  finishWorkoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 14,
    marginTop: 20,
    marginBottom: 8,
  },
  finishWorkoutBtnDisabled: {
    opacity: 0.6,
  },
  finishWorkoutBtnText: {
    fontSize: 17,
    fontWeight: '700',
    color: '#000',
  },
  // Complete modal styles
  completeModalContent: {
    alignItems: 'center',
    paddingVertical: 36,
    overflow: 'visible',
  },
  completeEmoji: {
    fontSize: 56,
    marginBottom: 12,
  },
  completeTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: colors.text,
    marginBottom: 20,
  },
  completeStreakBadge: {
    backgroundColor: '#FF6B6B20',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginBottom: 12,
  },
  completeStreakText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FF6B6B',
  },
  prSection: {
    width: '100%',
    marginTop: 12,
    gap: 8,
  },
  prRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: colors.primary + '15',
    borderRadius: 12,
    padding: 10,
  },
  prTrophy: {
    fontSize: 18,
    marginTop: 1,
  },
  prTextBlock: {
    flex: 1,
  },
  prExercise: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.text,
  },
  prDetail: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  addPhotoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 16,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
  },
  addPhotoBtnText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  sessionPhotoThumb: {
    width: '100%',
    height: 160,
    borderRadius: 12,
    marginTop: 14,
  },
  photoPickerModal: {
    paddingVertical: 8,
    paddingHorizontal: 0,
    alignItems: 'stretch',
    minWidth: 280,
  },
  photoPickerOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  photoPickerOptionText: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '500',
  },
  photoPickerDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginHorizontal: 20,
  },
  completeStatRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  completeStat: {
    fontSize: 16,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  completeDoneBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 40,
    paddingVertical: 14,
    borderRadius: 30,
    marginTop: 28,
  },
  completeDoneBtnText: {
    fontSize: 17,
    fontWeight: '700',
    color: '#000',
  },
});