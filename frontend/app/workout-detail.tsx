import React, { useEffect, useState } from 'react';
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
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

interface Exercise {
  name: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  instructions: string;
  muscle_groups: string[];
  equipment: string;
  gif_url?: string;
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
  focus_areas: string[];
  equipment: string[];
  days_per_week: number;
  workout_days: WorkoutDay[];
  created_at: string;
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
  // Performance tracking state: { "dayIndex-exerciseIndex-setIndex": { weight: "", reps: "", completed: false } }
  const [performance, setPerformance] = useState<Record<string, ExercisePerformance>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadWorkout();
  }, [id]);

  const loadWorkout = async () => {
    try {
      const response = await api.get(`/workout/${id}`);
      setWorkout(response.data);
      setNewName(response.data.name);
    } catch (error) {
      console.log('Error loading workout:', error);
    } finally {
      setLoading(false);
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
          </Text>
          
          <View style={styles.infoRow}>
            <View style={styles.infoItem}>
              <Ionicons name="calendar" size={20} color={colors.primary} />
              <Text style={styles.infoText}>{workout.days_per_week} days/week</Text>
            </View>
            <View style={styles.infoItem}>
              <Ionicons name="body" size={20} color={colors.primary} />
              <Text style={styles.infoText}>{workout.focus_areas.length} areas</Text>
            </View>
          </View>

          <View style={styles.tagContainer}>
            {workout.focus_areas.map((area, idx) => (
              <View key={idx} style={styles.tag}>
                <Text style={styles.tagText}>{area}</Text>
              </View>
            ))}
          </View>
        </View>

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
                      source={{ uri: exercise.gif_url }}
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
                      {exercise.sets} sets x {exercise.reps} reps • {exercise.rest_seconds}s rest
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
                          source={{ uri: exercise.gif_url }}
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
                        <Text style={styles.detailValue}>{exercise.equipment}</Text>
                      </View>
                      <View style={styles.detailItem}>
                        <Text style={styles.detailLabel}>Muscles</Text>
                        <Text style={styles.detailValue}>{exercise.muscle_groups.join(', ')}</Text>
                      </View>
                    </View>

                    {/* Performance Tracking */}
                    <View style={styles.trackingSection}>
                      <Text style={styles.trackingTitle}>Log Your Sets</Text>
                      {Array.from({ length: exercise.sets }, (_, setIdx) => {
                        const key = `${expandedDay}-${exIdx}-${setIdx}`;
                        const perf = performance[key] || { weight: '', reps: '', completed: false };
                        return (
                          <View key={setIdx} style={styles.setRow}>
                            <TouchableOpacity
                              style={[styles.setCheckbox, perf.completed && styles.setCheckboxChecked]}
                              onPress={() => {
                                setPerformance({
                                  ...performance,
                                  [key]: { ...perf, completed: !perf.completed },
                                });
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
                                setPerformance({
                                  ...performance,
                                  [key]: { ...perf, weight: text },
                                });
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
                                setPerformance({
                                  ...performance,
                                  [key]: { ...perf, reps: text },
                                });
                              }}
                            />
                          </View>
                        );
                      })}
                    </View>
                  </View>
                )}
              </TouchableOpacity>
            ))}
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
    backgroundColor: colors.surfaceLight,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagText: {
    fontSize: 12,
    color: colors.textSecondary,
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
});