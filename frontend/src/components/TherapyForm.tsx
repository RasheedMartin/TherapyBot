import {
  Box,
  Button,
  CircularProgress,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import api from "../api/client";

export const TherapyForm = () => {
  const [question, setQuestion] = useState("");
  const [therapyType, setTherapyType] = useState("");
  const [result, setResult] = useState("");

  const {
    data: response,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["therapy_session"],
    queryFn: () =>
      api.get("get_started", {
        question,
        therapy_type: therapyType,
      }),
    enabled: false,
    retry: false,
  });

  useEffect(() => {
    if (response) {
      setResult(response.data.answer);
    }
    if (error) {
      setResult("Something went wrong. Please try again.");
    }
  }, [response]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResult("");
    refetch();
  };

  console.log(response);
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
              disabled={isLoading}
              onClick={handleSubmit}
            >
              {isLoading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                "Submit"
              )}
            </Button>
          </Box>
        </Box>

        {result && (
          <Box mt={4} textAlign="center">
            <Typography variant="subtitle1" fontWeight={600}>
              Result:
            </Typography>
            <Typography
              variant="body1"
              sx={{
                mt: 1,
                p: 2,
                borderRadius: 2,
                backgroundColor: "grey.100",
              }}
            >
              {result}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
};
