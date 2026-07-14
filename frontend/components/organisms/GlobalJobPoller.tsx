"use client";

import { useEffect, useRef } from "react";
import { useUIStore } from "@/stores/uiStore";
import api from "@/lib/api";

const POLLING_INTERVAL = 10000; // 10 seconds

export function GlobalJobPoller() {
  const { addToast, setUnreadNotifications } = useUIStore();
  const activeJobsRef = useRef<Record<string, string>>({});

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const pollJobs = async () => {
      if (!localStorage.getItem("slm_token")) {
        timeoutId = setTimeout(pollJobs, POLLING_INTERVAL);
        return;
      }
      
      try {
        const response = await api.get("/projects/");
        const projects = response.data;

        if (Array.isArray(projects)) {
          projects.forEach((project: any) => {
            const currentStatus = project.status;
            const previousStatus = activeJobsRef.current[project.id];

            // If it transitioned to completed
            if (
              (previousStatus === "processing" || previousStatus === "training" || previousStatus === "pending") &&
              currentStatus === "completed"
            ) {
              // 1. In-App Toast
              addToast({
                message: `Model for project "${project.name}" is ready!`,
                type: "success",
              });

              // 2. Red dot on bell
              setUnreadNotifications(true);

              // 3. OS Native Notification (if granted)
              if ("Notification" in window && Notification.permission === "granted") {
                new Notification("SLM Studio: Training Complete", {
                  body: `Your model for "${project.name}" has finished training successfully!`,
                });
              }
            }
            
            // If it transitioned to failed
            if (
              (previousStatus === "processing" || previousStatus === "training" || previousStatus === "pending") &&
              currentStatus === "failed"
            ) {
              addToast({
                message: `Model for project "${project.name}" encountered an error during training.`,
                type: "error",
              });
              setUnreadNotifications(true);
              
              if ("Notification" in window && Notification.permission === "granted") {
                new Notification("SLM Studio: Training Failed", {
                  body: `Your model for "${project.name}" failed to train.`,
                });
              }
            }

            // Always update ref so we don't trigger again
            activeJobsRef.current[project.id] = currentStatus;
          });
        }
      } catch (error) {
        console.error("Failed to poll global jobs status:", error);
      } finally {
        timeoutId = setTimeout(pollJobs, POLLING_INTERVAL);
      }
    };

    pollJobs();

    return () => {
      clearTimeout(timeoutId);
    };
  }, [addToast, setUnreadNotifications]);

  return null;
}
