package com.example.applicationlightingcontrol;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

public class WorkplaceControl extends AppCompatActivity {

    private View colorIndicator;
    private SeekBar sbBrightness, sbWarmth;
    private CheckBox cbAutoMode;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_workplace_control);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        colorIndicator = findViewById(R.id.colorIndicator);
        sbBrightness = findViewById(R.id.sbBrightness);
        sbWarmth = findViewById(R.id.sbWarmth);
        cbAutoMode = findViewById(R.id.cbAutoMode);
        Spinner spinnerWorkplaces = findViewById(R.id.spinnerWorkplaces);
        Button btnSettings = findViewById(R.id.btnSettings);


        String[] workplaces = {"РАБОЧЕЕ МЕСТО 1", "РАБОЧЕЕ МЕСТО 2", "РАБОЧЕЕ МЕСТО 3"};

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, workplaces);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerWorkplaces.setAdapter(adapter);

        cbAutoMode.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                sbBrightness.setEnabled(!isChecked);

                sbBrightness.setAlpha(isChecked ? 0.3f : 1.0f);
            }
        });


        SeekBar.OnSeekBarChangeListener seekBarListener = new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                updateIndicatorColor();
            }
            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        };

        sbBrightness.setOnSeekBarChangeListener(seekBarListener);
        sbWarmth.setOnSeekBarChangeListener(seekBarListener);

        btnSettings.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Toast.makeText(WorkplaceControl.this, "Настройки пока в разработке", Toast.LENGTH_SHORT).show();
            }
        });

        spinnerWorkplaces.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                Toast.makeText(WorkplaceControl.this, "Выбрано: " + workplaces[position], Toast.LENGTH_SHORT).show();
            }
            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });

        updateIndicatorColor();
    }

    private void updateIndicatorColor() {
        int brightness = sbBrightness.getProgress();
        int warmth = sbWarmth.getProgress();

        float bFactor = brightness / 100f;

        float wFactor = warmth / 100f; // 0.0 (холод) -> 1.0 (тепло)

        int red = (int) ((0 * (1 - wFactor)) + (255 * wFactor));
        int green = (int) ((100 * (1 - wFactor)) + (255 * wFactor));
        int blue = (int) ((255 * (1 - wFactor)) + (0 * wFactor));

        red = (int) (red * bFactor);
        green = (int) (green * bFactor);
        blue = (int) (blue * bFactor);

        int finalColor = Color.rgb(red, green, blue);

        colorIndicator.setBackgroundColor(finalColor);
    }
}