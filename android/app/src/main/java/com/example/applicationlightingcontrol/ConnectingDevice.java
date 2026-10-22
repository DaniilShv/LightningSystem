package com.example.applicationlightingcontrol;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast; // <-- Импорт для всплывающего сообщения

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

public class ConnectingDevice extends AppCompatActivity {

    private EditText etDeviceCode;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_connecting_device);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        etDeviceCode = findViewById(R.id.etDeviceCode);
        Button myButton = findViewById(R.id.btnGoToControl);

        myButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {

                if (isConnectionValid()) {
                    Intent intent = new Intent(ConnectingDevice.this, WorkplaceControl.class);
                    startActivity(intent);
                } else {
                    Toast.makeText(ConnectingDevice.this, "Невозможно подключиться. Проверьте код.", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private boolean isConnectionValid() {
        String deviceName = etDeviceCode.getText().toString().trim();

        if (deviceName.isEmpty()) {
            return false;
        }

        // Если всё ок
        return true;
    }
}