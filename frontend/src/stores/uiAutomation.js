import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'ui-automation-selected-project-id'

export const useUiAutomationStore = defineStore('uiAutomation', () => {
  const selectedProjectId = ref(localStorage.getItem(STORAGE_KEY) || '')

  const setSelectedProject = (projectId) => {
    if (projectId === undefined || projectId === null || projectId === '') {
      selectedProjectId.value = ''
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    selectedProjectId.value = String(projectId)
    localStorage.setItem(STORAGE_KEY, selectedProjectId.value)
  }

  const resolveSelectedProjectId = (projects = []) => {
    if (!Array.isArray(projects) || projects.length === 0) {
      return ''
    }

    const matchedProject = projects.find(
      (project) => String(project.id) === String(selectedProjectId.value)
    )

    const resolvedProjectId = matchedProject ? matchedProject.id : projects[0].id
    setSelectedProject(resolvedProjectId)
    return resolvedProjectId
  }

  return {
    selectedProjectId,
    setSelectedProject,
    resolveSelectedProjectId
  }
})
