import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  TextInput,
  Modal,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

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
  training_notes?: string;
}

export default function WorkoutDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
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
  const [isAddMode, setIsAddMode] = useState(false);  // true = adding new, false = replacing
  const [addToDayIdx, setAddToDayIdx] = useState<number | null>(null);  // which day to add exercise to
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedMuscle, setSelectedMuscle] = useState<string | null>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    
    // Auto-save when checkbox is checked
    if (data.completed) {
      savePerformance(newPerformance);
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

  // Search exercises from ExerciseDB
  const searchExercises = async (query: string, muscle?: string) => {
    setSearching(true);
    try {
      const params = new URLSearchParams();
      if (query) params.append('search', query);
      if (muscle) params.append('muscle', muscle);
      // Limit to 50 to avoid API rate limiting
      params.append('limit', '50');
      
      const response = await api.get(`/exercises/search?${params.toString()}`);
      setSearchResults(response.data.exercises || []);
    } catch (error) {
      console.log('Search error:', error);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  // Debounced search function to reduce API calls
  const debouncedSearch = useCallback((query: string, muscle?: string) => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    setSearching(true);
    searchTimeoutRef.current = setTimeout(() => {
      searchExercises(query, muscle);
    }, 400); // 400ms debounce
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

  // Open modal in add mode
  const openAddExerciseModal = (dayIdx: number) => {
    setIsAddMode(true);
    setAddToDayIdx(dayIdx);
    setReplaceTarget(null);
    setShowReplaceModal(true);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedMuscle(null);
    // Load initial exercises
    searchExercises('', undefined);
  };

  // Open modal in replace mode
  const openReplaceExerciseModal = (dayIdx: number, exIdx: number) => {
    setIsAddMode(false);
    setReplaceTarget({ dayIdx, exIdx });
    setAddToDayIdx(null);
    setShowReplaceModal(true);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedMuscle(null);
    // Load initial exercises
    searchExercises('', undefined);
  };

  // Refresh GIF URLs for all exercises
  const [refreshingGifs, setRefreshingGifs] = useState(false);
  
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

            {/* Effort guideline — plain-English, no jargon */}
            <View style={styles.coachingRow}>
              <View style={styles.coachingIcon}>
                <Ionicons name="flame" size={16} color={colors.primary} />
              </View>
              <View style={styles.coachingContent}>
                <Text style={styles.coachingLabel}>How Hard to Train</Text>
                <Text style={styles.coachingValue}>
                  Each set should feel genuinely challenging. Finish with 1–3 reps still in you — not easy, not total failure. When a weight stops feeling hard, add a little more next session.
                </Text>
              </View>
            </View>

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
                {workout.weekly_structure.map((day, idx) => (
                  <View key={idx} style={styles.weeklyDayRow}>
                    <View style={styles.weeklyDayDot} />
                    <Text style={styles.weeklyDayText}>{day}</Text>
                  </View>
                ))}
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
              <Text style={styles.dayTitle}>{workout.workout_days[expandedDay].day}</Text>
              <View style={styles.dayMeta}>
                <Ionicons name="time" size={16} color={colors.textSecondary} />
                <Text style={styles.dayMetaText}>
                  ~{workout.workout_days[expandedDay].duration_minutes} min
                </Text>
              </View>
            </View>

            {workout.workout_days[expandedDay].notes && (
              <View style={styles.notesCard}>
                <Ionicons name="information-circle" size={18} color={colors.primary} />
                <Text style={styles.notesText}>{workout.workout_days[expandedDay].notes}</Text>
              </View>
            )}

            {/* Exercises */}
            {workout.workout_days[expandedDay].exercises.map((exercise, exIdx) => (
              <TouchableOpacity
                key={exIdx}
                style={styles.exerciseCard}
                onPress={() =>
                  setExpandedExercise(
                    expandedExercise === `${expandedDay}-${exIdx}` ? null : `${expandedDay}-${exIdx}`
                  )
                }
              >
                <View style={styles.exerciseHeader}>
                  {/* Exercise Illustration Thumbnail */}
                  {exercise.gif_url && (
                    <Image
                      source={{ uri: getFullGifUrl(exercise.gif_url) || '' }}
                      style={styles.exerciseThumbnail}
                      resizeMode="cover"
                    />
                  )}
                  {!exercise.gif_url && (
                    <View style={styles.exerciseNumber}>
                      <Text style={styles.exerciseNumberText}>{exIdx + 1}</Text>
                    </View>
                  )}
                  <View style={styles.exerciseInfo}>
                    <Text style={styles.exerciseName}>{exercise.name}</Text>
                    <Text style={styles.exerciseMeta}>
                      {exercise.sets} sets × {exercise.reps} reps • {exercise.rest_seconds}s rest
                    </Text>
                  </View>
                  <Ionicons
                    name={expandedExercise === `${expandedDay}-${exIdx}` ? 'chevron-up' : 'chevron-down'}
                    size={20}
                    color={colors.textSecondary}
                  />
                </View>

                {expandedExercise === `${expandedDay}-${exIdx}` && (
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
                    
                    {/* Substitution hint */}
                    {exercise.substitution_hint && (
                      <View style={styles.substitutionRow}>
                        <Ionicons name="swap-horizontal" size={14} color={colors.textSecondary} />
                        <Text style={styles.substitutionText}>
                          <Text style={styles.substitutionLabel}>Alternatives: </Text>
                          {exercise.substitution_hint}
                        </Text>
                      </View>
                    )}

                    {/* Performance Tracking */}
                    <View style={styles.trackingSection}>
                      <View style={styles.trackingHeader}>
                        <Text style={styles.trackingTitle}>Log Your Sets</Text>
                        <TouchableOpacity
                          style={styles.addSetBtn}
                          onPress={() => addSet(expandedDay, exIdx)}
                        >
                          <Ionicons name="add" size={18} color={colors.primary} />
                          <Text style={styles.addSetText}>Add Set</Text>
                        </TouchableOpacity>
                      </View>
                      {Array.from({ length: exercise.sets }, (_, setIdx) => {
                        const key = `${expandedDay}-${exIdx}-${setIdx}`;
                        const perf = performance[key] || { weight: '', reps: '', completed: false };
                        return (
                          <View key={setIdx} style={styles.setRow}>
                            <TouchableOpacity
                              style={[styles.setCheckbox, perf.completed && styles.setCheckboxChecked]}
                              onPress={() => {
                                updatePerformance(key, { ...perf, completed: !perf.completed });
                              }}
                            >
                              {perf.completed && <Ionicons name="checkmark" size={16} color={colors.background} />}
                            </TouchableOpacity>
                            <Text style={styles.setLabel}>Set {setIdx + 1}</Text>
                            <TextInput
                              style={styles.setInput}
                              placeholder="kg"
                              placeholderTextColor={colors.textMuted}
                              keyboardType="decimal-pad"
                              value={perf.weight}
                              onChangeText={(text) => {
                                updatePerformance(key, { ...perf, weight: text });
                              }}
                            />
                            <Text style={styles.setX}>×</Text>
                            <TextInput
                              style={styles.setInput}
                              placeholder="reps"
                              placeholderTextColor={colors.textMuted}
                              keyboardType="number-pad"
                              value={perf.reps}
                              onChangeText={(text) => {
                                updatePerformance(key, { ...perf, reps: text });
                              }}
                            />
                            {/* Remove Set Button */}
                            <TouchableOpacity
                              style={styles.removeSetBtn}
                              onPress={() => removeSet(expandedDay, exIdx)}
                            >
                              <Ionicons name="close-circle" size={22} color={colors.error} />
                            </TouchableOpacity>
                          </View>
                        );
                      })}
                    </View>

                    {/* Exercise Actions */}
                    <View style={styles.exerciseActions}>
                      <TouchableOpacity
                        style={styles.actionBtn}
                        onPress={() => openReplaceExerciseModal(expandedDay, exIdx)}
                      >
                        <Ionicons name="swap-horizontal" size={18} color={colors.primary} />
                        <Text style={styles.actionBtnText}>Replace</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.actionBtnDanger]}
                        onPress={() => deleteExercise(expandedDay, exIdx)}
                      >
                        <Ionicons name="trash-outline" size={18} color={colors.error} />
                        <Text style={[styles.actionBtnText, styles.actionBtnTextDanger]}>Delete</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              </TouchableOpacity>
            ))}
            
            {/* Add Exercise Button - at the end of exercise list */}
            <TouchableOpacity
              style={styles.addExerciseBtn}
              onPress={() => openAddExerciseModal(expandedDay)}
            >
              <Ionicons name="add-circle-outline" size={22} color={colors.primary} />
              <Text style={styles.addExerciseBtnText}>Add Exercise</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

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
                    {selectedMuscle ? 'Tap a muscle group above to browse exercises' : 'Select a muscle group to get started'}
                  </Text>
                </View>
              ) : (
                <>
                  <Text style={styles.resultsCount}>{searchResults.length} exercises found</Text>
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
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  dayTitle: {
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
});