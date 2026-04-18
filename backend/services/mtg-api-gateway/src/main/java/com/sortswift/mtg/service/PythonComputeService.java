package com.sortswift.mtg.service;

import com.sortswift.mtg.dto.ComputeResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class PythonComputeService {

    @Value("${backend.compute.root:../compute}")
    private String computeRoot;

    @Value("${backend.python.command:python}")
    private String pythonCommand;

    public ComputeResponse runJob(String jobType, List<String> args) throws IOException, InterruptedException {
        String normalized = jobType.toLowerCase(Locale.ROOT);
        JobDefinition job = resolveJob(normalized);

        Path scriptPath = Path.of(computeRoot, job.relativeScriptPath()).normalize();
        List<String> command = new ArrayList<>();
        command.add(pythonCommand);
        command.add(scriptPath.toString());
        if (args != null && !args.isEmpty()) {
            command.addAll(args);
        }

        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(Path.of(computeRoot).toFile());
        processBuilder.redirectErrorStream(true);

        Process process = processBuilder.start();

        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append(System.lineSeparator());
            }
        }

        int exitCode = process.waitFor();
        String status = exitCode == 0 ? "SUCCESS" : "FAILED";
        return new ComputeResponse(status, normalized, exitCode, output.toString().trim());
    }

    private JobDefinition resolveJob(String jobType) {
        Map<String, JobDefinition> jobs = Map.of(
                "arbitrage", new JobDefinition("arbitrage-engine/arbitrage_engine.py"),
                "scanner", new JobDefinition("Ollama-scanner/Current-version/optimized_scanner.py"),
                "analysis", new JobDefinition("MTGJSON-analysis/check_arbitrage.py"),
                "buylist", new JobDefinition("buylist-updater/atomic_empire_scraper.py")
        );

        JobDefinition job = jobs.get(jobType);
        if (job == null) {
            throw new IllegalArgumentException("Unsupported jobType: " + jobType);
        }
        return job;
    }

    private record JobDefinition(String relativeScriptPath) {
    }
}
