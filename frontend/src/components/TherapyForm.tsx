import React, { useState } from "react";
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  TextField,
  Typography,
  Alert,
} from "@mui/material";
import api from "../api/client";
import { AxiosError, type AxiosResponse } from "axios";
interface ApiResponse {
  response?: string;
  answer?: string;
  result?: string;
  error?: string;
}
export const TherapyForm = () => {
  const [question, setQuestion] = useState("");
  const [therapyType, setTherapyType] = useState("Family Therapy");
  const [result, setResult] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (
    e: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    e.preventDefault();

    if (!question.trim()) {
      setResult("Please enter a question.");
      return;
    }

    setResult("");
    setError("");
    setIsLoading(true);

    try {
      const response: AxiosResponse<ApiResponse> = await api.post<ApiResponse>(
        "get_started/",
        {
          question,
          therapy_type: therapyType,
        },
      );

      const resultText: string =
        response.data.response ??
        response.data.answer ??
        response.data.result ??
        JSON.stringify(response.data);

      setResult(resultText);
    } catch (err: unknown) {
      let message = "Something went wrong. Please try again.";

      if (err instanceof AxiosError) {
        message = err.response?.data?.error ?? err.message ?? message;
      }

      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 600, mx: "auto", mt: 6, p: 3 }}>
      <Paper
        elevation={3}
        sx={{ p: 4, borderRadius: 3, backgroundColor: "background.paper" }}
      >
        <Typography
          variant="h5"
          component="h1"
          fontWeight={600}
          textAlign="center"
          gutterBottom
        >
          Therapy Question Form
        </Typography>

        <Box component="form" onSubmit={handleSubmit} noValidate>
          <TextField
            fullWidth
            label="Therapy Type"
            variant="outlined"
            value={therapyType}
            onChange={(e) => setTherapyType(e.target.value)}
            margin="normal"
            placeholder="e.g. Family Therapy"
          />
          <TextField
            fullWidth
            label="Question"
            variant="outlined"
            multiline
            rows={4}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            margin="normal"
            placeholder="Enter your therapy question"
            required
          />
          <Box sx={{ mt: 3, display: "flex", justifyContent: "center" }}>
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={isLoading || !question.trim()}
            >
              {isLoading ? (
                <>
                  <CircularProgress size={24} color="inherit" sx={{ mr: 1 }} />
                  Processing...
                </>
              ) : (
                "Submit"
              )}
            </Button>
          </Box>
        </Box>

        {isLoading && (
          <Alert severity="info" sx={{ mt: 3 }}>
            Processing your question... This may take 30-60 seconds on first
            load.
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {error}
          </Alert>
        )}
        {result && !isLoading && (
          <Box mt={4}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Response:
            </Typography>
            <Paper
              elevation={0}
              sx={{ p: 2, borderRadius: 2, backgroundColor: "grey.100" }}
            >
              <Typography variant="body1" style={{ whiteSpace: "pre-wrap" }}>
                {result}
              </Typography>
            </Paper>
          </Box>
        )}
      </Paper>
    </Box>
  );
};
