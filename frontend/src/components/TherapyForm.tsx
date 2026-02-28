import React, { useState } from "react";
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  TextField,
  Typography,
  Alert,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  type SelectChangeEvent,
} from "@mui/material";
import api from "../api/client";
import { AxiosError, type AxiosResponse } from "axios";

interface ApiResponse {
  response?: string;
  answer?: string;
  result?: string;
  error?: string;
}

const THERAPY_TYPES = [
  "Family Therapy",
  "Cognitive Behavioural Therapy (CBT)",
  "Dialectical Behaviour Therapy (DBT)",
  "Teen Counseling",
  "Anxiety Support",
  "General Therapy",
];

export const TherapyForm = () => {
  const [question, setQuestion] = useState("");
  const [therapyType, setTherapyType] = useState("General Therapy");
  const [result, setResult] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleTherapyTypeChange = (e: SelectChangeEvent) => {
    setTherapyType(e.target.value);
  };

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
          <FormControl fullWidth margin="normal">
            <InputLabel id="therapy-type-label">Therapy Type</InputLabel>
            <Select
              labelId="therapy-type-label"
              value={therapyType}
              label="Therapy Type"
              onChange={handleTherapyTypeChange}
            >
              {THERAPY_TYPES.map((type) => (
                <MenuItem key={type} value={type}>
                  {type}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

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
            InputLabelProps={{ shrink: true }}
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
