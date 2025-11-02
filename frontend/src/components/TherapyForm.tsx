import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  TextField,
  Typography,
  Alert,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export const TherapyForm = () => {
  const [question, setQuestion] = useState("");
  const [therapyType, setTherapyType] = useState("Family Therapy");
  const [result, setResult] = useState("");

  const {
    data: response,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["therapy_session", question, therapyType],
    queryFn: () =>
      api.get("get_started", {
        params: {
          question: question,
          therapy_type: therapyType,
        },
      }),
    enabled: false,
    retry: false,
  });

  useEffect(() => {
    if (response) {
      console.log("Full response:", response);
      console.log("Response data:", response.data);

      // Try different possible response structures
      const resultText =
        response.data?.response ||
        response.data?.answer ||
        response.data?.result ||
        JSON.stringify(response.data);

      setResult(resultText);
    }

    if (error) {
      console.error("Error:", error);
      setResult("Something went wrong. Please try again.");
    }
  }, [response, error]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!question.trim()) {
      setResult("Please enter a question.");
      return;
    }

    setResult("");
    refetch();
  };

  return (
    <Box
      sx={{
        maxWidth: 600,
        mx: "auto",
        mt: 6,
        p: 3,
      }}
    >
      <Paper
        elevation={3}
        sx={{
          p: 4,
          borderRadius: 3,
          backgroundColor: "background.paper",
        }}
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

          <Box
            sx={{
              mt: 3,
              display: "flex",
              justifyContent: "center",
            }}
          >
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
            {error?.response?.data?.error ||
              error?.message ||
              "Something went wrong. Please try again."}
          </Alert>
        )}

        {result && !isLoading && (
          <Box mt={4}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Response:
            </Typography>
            <Paper
              elevation={0}
              sx={{
                p: 2,
                borderRadius: 2,
                backgroundColor: "grey.100",
              }}
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
